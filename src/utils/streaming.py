import asyncio
from typing import AsyncIterable
from aiogram.types import InputFile, BufferedInputFile


class StreamingInputFile(InputFile):
    def __init__(self, stream: AsyncIterable[bytes], filename: str, chunk_size: int = 65536):
        super().__init__(filename=filename, chunk_size=chunk_size)
        self.stream = stream

    async def read(self, bot):
        async for chunk in self.stream:
            yield chunk


async def stream_subprocess(command: list[str]) -> AsyncIterable[bytes]:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL
    )
    
    while True:
        chunk = await process.stdout.read(65536)
        if not chunk:
            break
        yield chunk

    await process.wait()
