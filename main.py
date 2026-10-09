import os

import uvicorn

from banking_api.settings import Settings


def main():
    Settings.from_environment()
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("banking_api.app:app", host="127.0.0.1", port=port, reload=False)


if __name__ == "__main__":
    main()
