import os
import sqlite3
from flask import Blueprint, jsonify, request, session, redirect
from werkzeug.security import generate_password_hash, check_password_hash

try:
    from authlib.integrations.flask_client import OAuth
except ImportError:
    OAuth = None

DB_PATH = os.getenv(
    "SOILSENSE_DB_PATH",
    os.path.join(os.path.dirname(__file__), "soilsense.db")
)
FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "https://soil-sense-frontend.onrender.com"
).rstrip("/")

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_auth_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT,
            google_id TEXT UNIQUE,
            auth_provider TEXT NOT NULL DEFAULT 'local',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def user_dict(row):
    if not row:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "auth_provider": row["auth_provider"],
        "created_at": row["created_at"],
    }


def login_session(row):
    session.clear()
    session["user_id"] = row["id"]
    session["user_email"] = row["email"]
    session.permanent = True


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not name or not email or not password:
        return jsonify(success=False, message="Name, email and password are required."), 400

    if len(password) < 8:
        return jsonify(success=False, message="Password must be at least 8 characters."), 400

    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM users WHERE email = ?", (email,)
    ).fetchone()

    if existing:
        conn.close()
        return jsonify(
            success=False,
            message="An account with this email already exists."
        ), 409

    cur = conn.execute(
        """INSERT INTO users
           (name, email, password_hash, auth_provider)
           VALUES (?, ?, ?, 'local')""",
        (name, email, generate_password_hash(password))
    )
    conn.commit()

    row = conn.execute(
        "SELECT * FROM users WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    conn.close()

    login_session(row)

    return jsonify(
        success=True,
        message="Account created successfully.",
        user=user_dict(row)
    ), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()

    if (
        not row
        or not row["password_hash"]
        or not check_password_hash(row["password_hash"], password)
    ):
        return jsonify(
            success=False,
            message="Invalid email or password."
        ), 401

    login_session(row)

    return jsonify(
        success=True,
        message="Login successful.",
        user=user_dict(row)
    )


@auth_bp.get("/me")
def me():
    user_id = session.get("user_id")

    if not user_id:
        return jsonify(
            success=False,
            message="Not logged in."
        ), 401

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()

    if not row:
        session.clear()
        return jsonify(
            success=False,
            message="Account not found."
        ), 401

    return jsonify(
        success=True,
        user=user_dict(row)
    )


@auth_bp.post("/logout")
def logout():
    session.clear()
    return jsonify(success=True, message="Logged out.")


def register_auth(app):
    app.secret_key = os.getenv(
        "SECRET_KEY",
        "CHANGE_THIS_SECRET_KEY_IN_RENDER"
    )

    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE="None",
        PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 30,
    )

    init_auth_db()

    # Create Google OAuth before registering the blueprint.
    # This is important: the Google callback route must exist when
    # Flask registers the blueprint.
    oauth = None
    google = None

    if (
        OAuth
        and os.getenv("GOOGLE_CLIENT_ID")
        and os.getenv("GOOGLE_CLIENT_SECRET")
    ):
        oauth = OAuth(app)

        google = oauth.register(
            name="google",
            client_id=os.environ["GOOGLE_CLIENT_ID"],
            client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
            server_metadata_url=(
                "https://accounts.google.com/.well-known/"
                "openid-configuration"
            ),
            client_kwargs={
                "scope": "openid email profile"
            },
        )

    if google:

        @auth_bp.get("/google")
        def google_login():
            redirect_uri = (
                f"{request.host_url.rstrip('/')}"
                "/api/auth/google/callback"
            )
            return google.authorize_redirect(redirect_uri)


        @auth_bp.get("/google/callback")
        def google_callback():
            try:
                token = google.authorize_access_token()

                userinfo = (
                    token.get("userinfo")
                    or google.userinfo()
                )

                google_id = str(userinfo["sub"])
                email = str(
                    userinfo["email"]
                ).strip().lower()

                name = str(
                    userinfo.get("name")
                    or email.split("@")[0]
                ).strip()

                conn = get_db()

                row = conn.execute(
                    """SELECT * FROM users
                       WHERE google_id = ? OR email = ?""",
                    (google_id, email)
                ).fetchone()

                if row:
                    conn.execute(
                        """UPDATE users
                           SET name = ?,
                               google_id = ?,
                               auth_provider = 'google'
                           WHERE id = ?""",
                        (name, google_id, row["id"])
                    )
                    conn.commit()

                    row = conn.execute(
                        "SELECT * FROM users WHERE id = ?",
                        (row["id"],)
                    ).fetchone()

                else:
                    cur = conn.execute(
                        """INSERT INTO users
                           (name, email, google_id, auth_provider)
                           VALUES (?, ?, ?, 'google')""",
                        (name, email, google_id, "google")
                    )
                    conn.commit()

                    row = conn.execute(
                        "SELECT * FROM users WHERE id = ?",
                        (cur.lastrowid,)
                    ).fetchone()

                conn.close()

                login_session(row)

                return redirect(FRONTEND_URL)

            except Exception as error:
                print("Google OAuth error:", error)
                return redirect(
                    FRONTEND_URL + "?auth=google_error"
                )

    else:

        @auth_bp.get("/google")
        def google_not_configured():
            return jsonify(
                success=False,
                message=(
                    "Google login is not configured on the server. "
                    "Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET "
                    "to the Render backend environment variables."
                )
            ), 503

        @auth_bp.get("/google/callback")
        def google_callback_not_configured():
            return redirect(
                FRONTEND_URL + "?auth=google_not_configured"
            )

    # Register the blueprint only AFTER all routes above are defined.
    app.register_blueprint(auth_bp)

    return app
