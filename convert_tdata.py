import argparse
import asyncio
import json
from typing import List, Optional

from web.services.tdata_converter import TDataConverter


async def amain(sessions: Optional[List[str]]) -> None:
	converter = TDataConverter()
	report = await converter.convert_many(sessions)
	print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Telethon .session → tdata")
	parser.add_argument(
		"sessions",
		nargs="*",
		help="Пути к .session (по умолчанию все из sessions/)",
	)
	args = parser.parse_args()
	asyncio.run(amain(args.sessions or None))
