import pytest

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "permissions": ["geolocation", "camera"],
        "geolocation": {"latitude": -7.979261, "longitude": 112.625760},
    }

@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    return {
        **browser_type_launch_args,
        "args": [
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
            "--allow-file-access-from-files",
        ],
    }
