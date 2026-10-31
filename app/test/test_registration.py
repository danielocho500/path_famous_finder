import asyncio
import json
import os
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["NEO4J_USER"] = "test"
os.environ["NEO4J_PASS"] = "test"

from modules.famous.models import PostFamous
from modules.famous.routes import register_famous
from services.images import upload_image_url


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.person = PostFamous(
            real_name="Ada Lovelace",
            best_known_for="Analytical Engine",
            principal_occupation="Mathematician",
            country="GB",
            city_born="London",
            date_born=date(1815, 12, 10),
            image_url="https://example.com/ada.jpg",
        )

    def test_saves_cloudinary_url_after_successful_upload(self):
        with (
            patch("modules.famous.routes.uuid4", return_value=SimpleNamespace(hex="image123")),
            patch("modules.famous.routes.upload_image_url", return_value=(200, "https://res.cloudinary.com/ada.jpg")) as upload,
            patch("modules.famous.routes.save_new_famous", return_value=(201, "node123")) as save,
            patch("modules.famous.routes.delete_image") as delete,
        ):
            response = asyncio.run(register_famous(self.person))

        self.assertEqual(response.status_code, 201)
        self.assertEqual(json.loads(response.body)["message"], "famoso registrado")
        upload.assert_called_once_with(self.person.image_url, "famous", "image123")
        self.assertEqual(save.call_args.args[0].image_url, "https://res.cloudinary.com/ada.jpg")
        delete.assert_not_called()

    def test_does_not_create_person_when_image_upload_fails(self):
        with (
            patch("modules.famous.routes.upload_image_url", return_value=(500, "Server error")),
            patch("modules.famous.routes.save_new_famous") as save,
        ):
            response = asyncio.run(register_famous(self.person))

        self.assertEqual(response.status_code, 502)
        save.assert_not_called()

    def test_removes_image_when_database_write_fails(self):
        with (
            patch("modules.famous.routes.uuid4", return_value=SimpleNamespace(hex="image123")),
            patch("modules.famous.routes.upload_image_url", return_value=(200, "https://res.cloudinary.com/ada.jpg")),
            patch("modules.famous.routes.save_new_famous", return_value=(500, "error")),
            patch("modules.famous.routes.delete_image") as delete,
        ):
            response = asyncio.run(register_famous(self.person))

        self.assertEqual(response.status_code, 500)
        delete.assert_called_once_with("famous", "image123")

    def test_upload_returns_cloudinary_url(self):
        response = Mock(content=b"image contents")
        with (
            patch("services.images.requests.get", return_value=response),
            patch("services.images.cloudinary.uploader.upload", return_value={"secure_url": "https://res.cloudinary.com/ada.jpg"}),
        ):
            result = upload_image_url(self.person.image_url, "famous", "image123")

        self.assertEqual(result, (200, "https://res.cloudinary.com/ada.jpg"))

    def test_upload_without_cloudinary_url_removes_image(self):
        response = Mock(content=b"image contents")
        with (
            patch("services.images.requests.get", return_value=response),
            patch("services.images.cloudinary.uploader.upload", return_value={}),
            patch("services.images.delete_image") as delete,
        ):
            result = upload_image_url(self.person.image_url, "famous", "image123")

        self.assertEqual(result, (500, "Server error"))
        delete.assert_called_once_with("famous", "image123")

    def test_neo4j_driver_closes_after_application_lifespan(self):
        with patch("logs.logs.configure_logging"):
            import main

        async def run_lifespan():
            async with main.lifespan(main.app):
                driver.verify_connectivity.assert_called_once()
                driver.close.assert_not_called()

        with patch.object(main, "driver") as driver, patch.object(main.graph_repo, "ensure_schema") as schema:
            asyncio.run(run_lifespan())
            schema.assert_called_once()
            driver.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
