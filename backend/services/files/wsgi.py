from dotenv import load_dotenv

load_dotenv()

from app.factory import build_app  # noqa: E402

app = build_app()
