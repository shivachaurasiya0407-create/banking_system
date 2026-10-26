import os

import uvicorn

from banking_api.settings import Settings


def main():
    Settings.from_environment()
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "127.0.0.1")
    uvicorn.run("banking_api.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
