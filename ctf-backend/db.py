from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal

import oracledb

from config import Config


def validate_db_config() -> None:
    if not Config.ORACLE_USER or not Config.ORACLE_PASSWORD or not Config.ORACLE_DSN:
        raise ValueError("Missing Oracle environment variables")


def _oracle_error_code(exception: Exception) -> int | None:
    details = exception.args[0] if getattr(exception, "args", None) else None
    return getattr(details, "code", None)


def _number_var_to_int(var) -> int:
    value = var.getvalue()
    if isinstance(value, (list, tuple)):
        if not value:
            raise ValueError("No value returned from database insert")
        value = value[0]
    return int(value)


def _execute_insert_with_pk_fallback(
    cursor,
    identity_sql: str,
    identity_params,
    sequence_sql: str,
    sequence_params,
) -> None:
    try:
        cursor.execute(identity_sql, identity_params)
    except oracledb.DatabaseError as ex:
        # ORA-01400 means PK couldn't be auto-generated (legacy sequence schema).
        if _oracle_error_code(ex) != 1400:
            raise
        cursor.execute(sequence_sql, sequence_params)


def _progressive_award(points: int, attempt_no: int) -> int:
    if attempt_no <= 1:
        multiplier = 1.0
    elif attempt_no == 2:
        multiplier = 0.85
    elif attempt_no == 3:
        multiplier = 0.65
    elif attempt_no == 4:
        multiplier = 0.50
    elif attempt_no == 5:
        multiplier = 0.40
    else:
        multiplier = 0.15
    return max(int(round(points * multiplier)), 0)


def _progressive_award_db_or_python(cursor, points: int, attempt_no: int) -> int:
    try:
        cursor.execute(
            "SELECT fn_progressive_award(:1, :2) FROM dual",
            (points, attempt_no),
        )
        row = cursor.fetchone()
        if row and row[0] is not None:
            return int(row[0])
    except oracledb.DatabaseError:
        # Backward-compatible fallback when schema objects are not yet migrated.
        pass
    return _progressive_award(points, attempt_no)


@contextmanager
def get_connection():
    validate_db_config()
    connection = oracledb.connect(
        user=Config.ORACLE_USER,
        password=Config.ORACLE_PASSWORD,
        dsn=Config.ORACLE_DSN,
    )
    try:
        yield connection
    finally:
        connection.close()


def _normalize_value(value):
    if isinstance(value, Decimal):
        return int(value) if value == int(value) else float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if hasattr(value, "read"):
        return value.read()
    return value


def _as_dict_list(cursor, rows):
    columns = [col[0].lower() for col in cursor.description]
    normalized_rows = []
    for row in rows:
        normalized_rows.append(
            {
                columns[index]: _normalize_value(value)
                for index, value in enumerate(row)
            }
        )
    return normalized_rows


def _first_challenge_no(cursor) -> int | None:
    cursor.execute("SELECT MIN(challenge_no) FROM challenge WHERE is_active = 1")
    row = cursor.fetchone()
    if not row or row[0] is None:
        return None
    return int(row[0])


def _next_challenge_no(cursor, current_challenge_no: int) -> int | None:
    cursor.execute(
        """
        SELECT MIN(challenge_no)
        FROM challenge
        WHERE challenge_no > :1
          AND is_active = 1
        """,
        (current_challenge_no,),
    )
    row = cursor.fetchone()
    if not row or row[0] is None:
        return None
    return int(row[0])


def _ensure_current_challenge_no(cursor, team_id: int, lock_row: bool = False) -> int | None:
    query = "SELECT current_challenge_no FROM team WHERE team_id = :1"
    if lock_row:
        query += " FOR UPDATE"

    cursor.execute(query, (team_id,))
    row = cursor.fetchone()
    if not row:
        raise ValueError("Team not found")

    current = int(row[0]) if row[0] is not None else None
    if current is not None:
        cursor.execute(
            """
            SELECT challenge_no
            FROM challenge
            WHERE challenge_no = :1
              AND is_active = 1
            """,
            (current,),
        )
        active_row = cursor.fetchone()
        if active_row:
            return current

        next_active = _next_challenge_no(cursor, current)
        cursor.execute(
            """
            UPDATE team
            SET current_challenge_no = :1
            WHERE team_id = :2
            """,
            (next_active, team_id),
        )
        return next_active

    # If current is None, they either haven't started or they finished everything available previously.
    # Find the lowest active challenge they HAVEN'T solved correctly.
    cursor.execute(
        """
        SELECT MIN(c.challenge_no)
        FROM challenge c
        WHERE c.is_active = 1
          AND NOT EXISTS (
              SELECT 1
              FROM submission s
              WHERE s.team_id = :1
                AND s.challenge_no = c.challenge_no
                AND s.is_correct = 1
          )
        """,
        (team_id,),
    )
    unsolved_row = cursor.fetchone()
    next_unsolved = int(unsolved_row[0]) if unsolved_row and unsolved_row[0] is not None else None

    # Update team with what we found (could be a valid ID or None if they've solved everything)
    cursor.execute(
        """
        UPDATE team
        SET current_challenge_no = :1
        WHERE team_id = :2
        """,
        (next_unsolved, team_id),
    )
    return next_unsolved


def ping_database() -> dict:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 'OK' AS status FROM dual")
            row = cursor.fetchone()
            return {
                "database": "oracle",
                "status": row[0] if row else "UNKNOWN",
            }


def register_student(name: str, email: str, team_name: str) -> dict:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT student_id
                FROM student
                WHERE LOWER(email) = LOWER(:1)
                """,
                (email,),
            )
            if cursor.fetchone():
                raise ValueError("Email already registered")

            cursor.execute(
                """
                SELECT team_id, team_name, score
                FROM team
                WHERE LOWER(team_name) = LOWER(:1)
                """,
                (team_name,),
            )
            team_row = cursor.fetchone()

            if team_row:
                team_id = int(team_row[0])
                stored_team_name = team_row[1]
                score = int(team_row[2])
            else:
                team_id_var = cursor.var(oracledb.NUMBER)
                _execute_insert_with_pk_fallback(
                    cursor,
                    identity_sql="""
                    INSERT INTO team (team_name, score)
                    VALUES (:1, 0)
                    RETURNING team_id INTO :2
                    """,
                    identity_params=(team_name, team_id_var),
                    sequence_sql="""
                    INSERT INTO team (team_id, team_name, score)
                    VALUES (team_seq.NEXTVAL, :1, 0)
                    RETURNING team_id INTO :2
                    """,
                    sequence_params=(team_name, team_id_var),
                )
                team_id = _number_var_to_int(team_id_var)
                stored_team_name = team_name
                score = 0

            current_challenge_no = _ensure_current_challenge_no(cursor, team_id=team_id, lock_row=True)

            student_id_var = cursor.var(oracledb.NUMBER)
            _execute_insert_with_pk_fallback(
                cursor,
                identity_sql="""
                INSERT INTO student (name, email, team_id)
                VALUES (:1, :2, :3)
                RETURNING student_id INTO :4
                """,
                identity_params=(name, email, team_id, student_id_var),
                sequence_sql="""
                INSERT INTO student (student_id, name, email, team_id)
                VALUES (student_seq.NEXTVAL, :1, :2, :3)
                RETURNING student_id INTO :4
                """,
                sequence_params=(name, email, team_id, student_id_var),
            )
            student_id = _number_var_to_int(student_id_var)
            connection.commit()

            return {
                "student_id": student_id,
                "name": name,
                "email": email,
                "team_id": team_id,
                "team_name": stored_team_name,
                "score": score,
                "current_challenge_no": current_challenge_no,
            }


def login_student(email: str) -> dict:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT student_id, name, email, team_id
                FROM student
                WHERE LOWER(email) = LOWER(:1)
                """,
                (email,),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError("Student not found")

            student_id = int(row[0])
            name = row[1]
            found_email = row[2]
            team_id = int(row[3]) if row[3] is not None else None

            team_name = None
            score = 0
            current_challenge_no = None

            if team_id is not None:
                current_challenge_no = _ensure_current_challenge_no(cursor, team_id=team_id)
                cursor.execute(
                    """
                    SELECT team_name, score
                    FROM team
                    WHERE team_id = :1
                    """,
                    (team_id,),
                )
                team_row = cursor.fetchone()
                if team_row:
                    team_name = team_row[0]
                    score = int(team_row[1])

            connection.commit()
            return {
                "student_id": student_id,
                "name": name,
                "email": found_email,
                "team_id": team_id,
                "team_name": team_name,
                "score": score,
                "current_challenge_no": current_challenge_no,
            }


def get_team_progress(team_id: int) -> dict:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            current_challenge_no = _ensure_current_challenge_no(cursor, team_id=team_id)
            cursor.execute(
                """
                SELECT team_id, team_name, score, current_challenge_no
                FROM team
                WHERE team_id = :1
                """,
                (team_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError("Team not found")

            connection.commit()
            return {
                "team_id": int(row[0]),
                "team_name": row[1],
                "score": int(row[2]),
                "current_challenge_no": int(row[3]) if row[3] is not None else current_challenge_no,
            }


def list_categories() -> list:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT category_id, category_name, description
                FROM category
                ORDER BY category_id
                """
            )
            rows = cursor.fetchall()
            return _as_dict_list(cursor, rows)


def list_challenges(category_id: int | None = None, team_id: int | None = None) -> list:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            if team_id is not None:
                current_challenge_no = _ensure_current_challenge_no(cursor, team_id=team_id)
                if current_challenge_no is None:
                    connection.commit()
                    return []

                if category_id is None:
                    cursor.execute(
                        """
                        SELECT challenge_no, question_text, points, category_id
                        FROM challenge
                        WHERE challenge_no = :1
                          AND is_active = 1
                        """,
                        (current_challenge_no,),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT challenge_no, question_text, points, category_id
                        FROM challenge
                        WHERE challenge_no = :1
                          AND category_id = :2
                          AND is_active = 1
                        """,
                        (current_challenge_no, category_id),
                    )
                rows = cursor.fetchall()
                connection.commit()
                return _as_dict_list(cursor, rows)

            if category_id is None:
                cursor.execute(
                    """
                    SELECT challenge_no, question_text, points, category_id
                    FROM challenge
                    WHERE is_active = 1
                    ORDER BY challenge_no
                    """
                )
            else:
                cursor.execute(
                    """
                    SELECT challenge_no, question_text, points, category_id
                    FROM challenge
                    WHERE category_id = :1
                      AND is_active = 1
                    ORDER BY challenge_no
                    """,
                    (category_id,),
                )
            rows = cursor.fetchall()
            return _as_dict_list(cursor, rows)


def list_hints(challenge_no: int) -> list:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT hint_id, hint_text, penalty_points
                FROM hint
                WHERE challenge_no = :1
                ORDER BY hint_id
                """,
                (challenge_no,),
            )
            rows = cursor.fetchall()
            return _as_dict_list(cursor, rows)


def unlock_hint(team_id: int, hint_id: int) -> dict:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            current_challenge_no = _ensure_current_challenge_no(cursor, team_id=team_id, lock_row=True)

            cursor.execute(
                """
                SELECT challenge_no, penalty_points
                FROM hint
                WHERE hint_id = :1
                """,
                (hint_id,),
            )
            hint_row = cursor.fetchone()
            if not hint_row:
                raise ValueError("Hint not found")

            hint_challenge_no = int(hint_row[0])
            penalty = int(hint_row[1])

            if current_challenge_no is None or hint_challenge_no != current_challenge_no:
                raise ValueError("Hints can be unlocked only for the current challenge")

            cursor.execute(
                """
                SELECT usage_id
                FROM hint_usage
                WHERE team_id = :1 AND hint_id = :2
                """,
                (team_id, hint_id),
            )
            existing = cursor.fetchone()
            if existing:
                cursor.execute(
                    """
                    SELECT score
                    FROM team
                    WHERE team_id = :1
                    """,
                    (team_id,),
                )
                score_row = cursor.fetchone()
                connection.commit()
                return {
                    "already_unlocked": True,
                    "penalty_points": 0,
                    "team_score": int(score_row[0]) if score_row else 0,
                }

            _execute_insert_with_pk_fallback(
                cursor,
                identity_sql="""
                INSERT INTO hint_usage (team_id, hint_id)
                VALUES (:1, :2)
                """,
                identity_params=(team_id, hint_id),
                sequence_sql="""
                INSERT INTO hint_usage (usage_id, team_id, hint_id)
                VALUES (hint_usage_seq.NEXTVAL, :1, :2)
                """,
                sequence_params=(team_id, hint_id),
            )

            if penalty > 0:
                cursor.execute(
                    """
                    UPDATE team
                    SET score = GREATEST(score - :1, 0)
                    WHERE team_id = :2
                    """,
                    (penalty, team_id),
                )

            cursor.execute(
                """
                SELECT score
                FROM team
                WHERE team_id = :1
                """,
                (team_id,),
            )
            score_row = cursor.fetchone()
            connection.commit()
            return {
                "already_unlocked": False,
                "penalty_points": penalty,
                "team_score": int(score_row[0]) if score_row else 0,
            }


def create_submission(team_id: int, student_id: int, challenge_no: int, submitted_answer: str) -> dict:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT team_id
                FROM student
                WHERE student_id = :1
                """,
                (student_id,),
            )
            student_row = cursor.fetchone()
            if not student_row:
                raise ValueError("Student not found")

            student_team_id = int(student_row[0]) if student_row[0] is not None else None
            if student_team_id != team_id:
                raise ValueError("Student does not belong to the provided team")

            current_challenge_no = _ensure_current_challenge_no(cursor, team_id=team_id, lock_row=True)
            if current_challenge_no is None:
                raise ValueError("No challenges available")

            if challenge_no != current_challenge_no:
                raise ValueError(f"Submit only for current challenge #{current_challenge_no}")

            cursor.execute(
                """
                SELECT answer, points
                FROM challenge
                WHERE challenge_no = :1
                  AND is_active = 1
                """,
                (current_challenge_no,),
            )
            challenge_row = cursor.fetchone()
            if not challenge_row:
                raise ValueError("Challenge not found or inactive")

            expected_answer = str(challenge_row[0]).strip()
            points = int(challenge_row[1])
            normalized_submitted = submitted_answer.strip()
            is_correct = int(expected_answer == normalized_submitted)

            cursor.execute(
                """
                SELECT COUNT(1)
                FROM submission
                WHERE team_id = :1
                  AND challenge_no = :2
                """,
                (team_id, current_challenge_no),
            )
            attempts_row = cursor.fetchone()
            previous_attempts = int(attempts_row[0]) if attempts_row and attempts_row[0] is not None else 0
            attempt_no = previous_attempts + 1

            _execute_insert_with_pk_fallback(
                cursor,
                identity_sql="""
                INSERT INTO submission (
                    team_id,
                    student_id,
                    challenge_no,
                    submitted_answer,
                    is_correct
                ) VALUES (
                    :1,
                    :2,
                    :3,
                    :4,
                    :5
                )
                """,
                identity_params=(
                    team_id,
                    student_id,
                    current_challenge_no,
                    normalized_submitted,
                    is_correct,
                ),
                sequence_sql="""
                INSERT INTO submission (
                    submission_id,
                    team_id,
                    student_id,
                    challenge_no,
                    submitted_answer,
                    is_correct
                ) VALUES (
                    submission_seq.NEXTVAL,
                    :1,
                    :2,
                    :3,
                    :4,
                    :5
                )
                """,
                sequence_params=(
                    team_id,
                    student_id,
                    current_challenge_no,
                    normalized_submitted,
                    is_correct,
                ),
            )

            awarded_points = 0
            next_challenge_no = current_challenge_no

            if is_correct:
                awarded_points = _progressive_award_db_or_python(cursor, points, attempt_no)
                next_challenge_no = _next_challenge_no(cursor, current_challenge_no)
                cursor.execute(
                    """
                    UPDATE team
                    SET score = score + :1,
                        current_challenge_no = :2
                    WHERE team_id = :3
                    """,
                    (
                        awarded_points,
                        next_challenge_no,
                        team_id,
                    ),
                )

            cursor.execute(
                """
                SELECT score
                FROM team
                WHERE team_id = :1
                """,
                (team_id,),
            )
            score_row = cursor.fetchone()
            team_score = int(score_row[0]) if score_row else 0

            connection.commit()
            return {
                "is_correct": bool(is_correct),
                "awarded_points": awarded_points,
                "team_score": team_score,
                "current_challenge_no": next_challenge_no,
                "event_completed": bool(is_correct and next_challenge_no is None),
            }


def get_leaderboard() -> list:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            try:
                result_cursor = connection.cursor()
                cursor.callproc("sp_get_leaderboard", [result_cursor])
                rows = result_cursor.fetchall()
                return _as_dict_list(result_cursor, rows)
            except oracledb.DatabaseError:
                cursor.execute(
                    """
                    SELECT team_id, team_name, score
                    FROM team
                    ORDER BY score DESC, team_name ASC
                    """
                )
                rows = cursor.fetchall()
                return _as_dict_list(cursor, rows)


def list_admin_submissions() -> list:
        with get_connection() as connection:
                with connection.cursor() as cursor:
                        cursor.execute(
                                """
                                SELECT
                                        s.submission_id,
                                        t.team_id,
                                        t.team_name,
                                        st.student_id,
                                        st.name AS student_name,
                                        s.challenge_no,
                                        s.submitted_answer,
                                        s.is_correct
                                FROM submission s
                                LEFT JOIN team t
                                    ON t.team_id = s.team_id
                                LEFT JOIN student st
                                    ON st.student_id = s.student_id
                                ORDER BY s.submission_id DESC
                                """
                        )
                        rows = cursor.fetchall()
                        return _as_dict_list(cursor, rows)


def list_admin_challenges(category_id: int | None = None) -> list:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            if category_id is None:
                cursor.execute(
                    """
                    SELECT challenge_no, question_text, answer, points, category_id, is_active
                    FROM challenge
                    WHERE is_active = 1
                    ORDER BY challenge_no DESC
                    """
                )
            else:
                cursor.execute(
                    """
                    SELECT challenge_no, question_text, answer, points, category_id, is_active
                    FROM challenge
                    WHERE category_id = :1 AND is_active = 1
                    ORDER BY challenge_no DESC
                    """,
                    (category_id,),
                )
            rows = cursor.fetchall()
            return _as_dict_list(cursor, rows)


def list_admin_first_bloods() -> list:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    fb.challenge_no,
                    c.question_text,
                    fb.team_id,
                    t.team_name,
                    fb.student_id,
                    st.name AS student_name,
                    fb.submission_id,
                    fb.awarded_at
                FROM challenge_first_blood fb
                JOIN challenge c
                    ON c.challenge_no = fb.challenge_no
                JOIN team t
                    ON t.team_id = fb.team_id
                JOIN student st
                    ON st.student_id = fb.student_id
                ORDER BY fb.awarded_at DESC
                """
            )
            rows = cursor.fetchall()
            return _as_dict_list(cursor, rows)


def create_category(category_name: str, description: str | None = None) -> dict:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            category_id_var = cursor.var(oracledb.NUMBER)
            _execute_insert_with_pk_fallback(
                cursor,
                identity_sql="""
                INSERT INTO category (category_name, description)
                VALUES (:1, :2)
                RETURNING category_id INTO :3
                """,
                identity_params=(
                    category_name,
                    description,
                    category_id_var,
                ),
                sequence_sql="""
                INSERT INTO category (category_id, category_name, description)
                VALUES (category_seq.NEXTVAL, :1, :2)
                RETURNING category_id INTO :3
                """,
                sequence_params=(
                    category_name,
                    description,
                    category_id_var,
                ),
            )
            category_id = _number_var_to_int(category_id_var)
            connection.commit()
            return {"category_id": category_id, "category_name": category_name}


def create_challenge(category_id: int, question_text: str, answer: str, points: int) -> dict:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            challenge_no_var = cursor.var(oracledb.NUMBER)
            _execute_insert_with_pk_fallback(
                cursor,
                identity_sql="""
                INSERT INTO challenge (question_text, answer, points, category_id)
                VALUES (:1, :2, :3, :4)
                RETURNING challenge_no INTO :5
                """,
                identity_params=(
                    question_text,
                    answer,
                    points,
                    category_id,
                    challenge_no_var,
                ),
                sequence_sql="""
                INSERT INTO challenge (challenge_no, question_text, answer, points, category_id)
                VALUES (challenge_seq.NEXTVAL, :1, :2, :3, :4)
                RETURNING challenge_no INTO :5
                """,
                sequence_params=(
                    question_text,
                    answer,
                    points,
                    category_id,
                    challenge_no_var,
                ),
            )
            challenge_no = _number_var_to_int(challenge_no_var)

            cursor.execute(
                """
                UPDATE team
                SET current_challenge_no = (
                    SELECT MIN(challenge_no)
                    FROM challenge
                    WHERE is_active = 1
                )
                WHERE current_challenge_no IS NULL
                  AND NOT EXISTS (
                      SELECT 1
                      FROM submission s
                      WHERE s.team_id = team.team_id
                        AND s.is_correct = 1
                  )
                """
            )

            connection.commit()
            return {"challenge_no": int(challenge_no)}


def deactivate_challenge(challenge_no: int) -> dict:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT is_active
                FROM challenge
                WHERE challenge_no = :1
                FOR UPDATE
                """,
                (challenge_no,),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError("Challenge not found")

            is_active = int(row[0]) if row[0] is not None else 0
            if is_active == 0:
                connection.commit()
                return {
                    "challenge_no": challenge_no,
                    "is_active": False,
                    "already_inactive": True,
                }

            cursor.execute(
                """
                UPDATE challenge
                SET is_active = 0
                WHERE challenge_no = :1
                """,
                (challenge_no,),
            )

            cursor.execute(
                """
                UPDATE team t
                SET current_challenge_no = (
                    SELECT MIN(c.challenge_no)
                    FROM challenge c
                    WHERE c.is_active = 1
                      AND c.challenge_no > t.current_challenge_no
                )
                WHERE t.current_challenge_no = :1
                """,
                (challenge_no,),
            )

            connection.commit()
            return {
                "challenge_no": challenge_no,
                "is_active": False,
                "already_inactive": False,
            }
