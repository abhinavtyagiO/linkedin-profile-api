import tempfile
import unittest
from pathlib import Path

from linkedin_profile_api.config import ConfigurationError, LinkedInCredentials, read_dotenv


class ConfigTests(unittest.TestCase):
    def test_reads_quoted_values_without_exposing_them_in_repr(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("LINKEDIN_LI_AT=secret-a\nLINKEDIN_JSESSIONID='ajax:123'\n")
            credentials = LinkedInCredentials.load(path, environ={})

        self.assertEqual(credentials.csrf_token, "ajax:123")
        self.assertTrue(credentials.cookie_header.endswith("lang=v=2&lang=en-us"))
        self.assertNotIn("secret-a", repr(credentials))
        self.assertNotIn("ajax:123", repr(credentials))

    def test_missing_values_names_keys_only(self):
        with self.assertRaises(ConfigurationError) as context:
            LinkedInCredentials.load(Path("does-not-exist"), environ={})
        self.assertIn("LINKEDIN_LI_AT", str(context.exception))
        self.assertIn("LINKEDIN_JSESSIONID", str(context.exception))

    def test_rejects_invalid_dotenv_line(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("not-an-assignment\n")
            with self.assertRaises(ConfigurationError):
                read_dotenv(path)


if __name__ == "__main__":
    unittest.main()
