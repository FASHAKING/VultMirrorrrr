"""Offline regression tests for VultMirror's local behavior."""

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from bot import MultiUserCABot
from database import Database


BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def base58_encode(data: bytes) -> str:
    """Encode bytes for creating deterministic public-key test fixtures."""
    number = int.from_bytes(data, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = BASE58_ALPHABET[remainder] + encoded
    return "1" * (len(data) - len(data.lstrip(b"\0"))) + (encoded or "1")


class SolanaDetectionTests(unittest.TestCase):
    def setUp(self):
        # These helpers do not need the bot's database or Telegram clients.
        self.bot = MultiUserCABot.__new__(MultiUserCABot)
        self.address = base58_encode(bytes(range(1, 33)))

    def test_accepts_a_32_byte_base58_public_key(self):
        self.assertTrue(self.bot.is_valid_solana_address(self.address))

    def test_rejects_a_base58_value_that_is_not_32_bytes(self):
        self.assertFalse(self.bot.is_valid_solana_address("2" * 32))

    def test_extracts_a_standalone_ca_and_ignores_url_embedded_ca(self):
        message = f"CA: {self.address}\nhttps://dexscreener.com/solana/{self.address}"
        self.assertEqual(self.bot.extract_solana_cas(message), self.address)
        self.assertIsNone(self.bot.extract_solana_cas(f"https://dexscreener.com/solana/{self.address}"))

    def test_extracts_supported_trading_link(self):
        link = "https://pump.fun/coin/ExampleToken123"
        self.assertEqual(self.bot.extract_trading_links(f"Trade here: {link}"), link)


class DatabaseTests(unittest.TestCase):
    def test_db_path_environment_variable_is_used(self):
        original_cwd = Path.cwd()
        original_db_path = os.environ.get("DB_PATH")
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                # Database currently loads the checked-in schema relative to
                # the working directory, matching the bot's service setup.
                Path("schema.sql").write_text((original_cwd / "schema.sql").read_text())
                db_file = Path(directory) / "vultmirror.db"
                os.environ["DB_PATH"] = str(db_file)
                database = Database()
                self.assertEqual(Path(database.db_path), db_file)
                self.assertTrue(db_file.exists())
            finally:
                os.chdir(original_cwd)
                if original_db_path is None:
                    os.environ.pop("DB_PATH", None)
                else:
                    os.environ["DB_PATH"] = original_db_path


class CommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_stats_requires_start_for_unknown_user(self):
        bot = MultiUserCABot.__new__(MultiUserCABot)
        bot.db = Mock()
        bot.db.get_user_stats.return_value = {}
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=123),
            message=message,
        )

        await bot.stats_command(update, SimpleNamespace())

        message.reply_text.assert_awaited_once_with(
            "Use /start first to create your VultMirror account."
        )


if __name__ == "__main__":
    unittest.main()
