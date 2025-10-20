"""Docker PostgreSQL container management utilities."""

import subprocess
import time
from typing import Optional, Dict

from src.utils.pipeline_logging import get_logger

logger = get_logger(__name__)


class DockerPostgreSQLManager:
    """Manages Docker PostgreSQL container lifecycle for verification."""

    def __init__(
        self,
        container_name: str = "oevk-verify",
        port: int = 5432,
        database: str = "oevk",
        user: str = "oevk",
        password: str = "oevk",
    ):
        """Initialize Docker PostgreSQL manager.

        Args:
            container_name: Name for the Docker container
            port: PostgreSQL port (default: 5432)
            database: Database name (default: oevk)
            user: PostgreSQL user (default: oevk)
            password: PostgreSQL password (default: oevk)
        """
        self.container_name = container_name
        self.port = port
        self.database = database
        self.user = user
        self.password = password

    def create_container(self) -> str:
        """Create and start a PostgreSQL Docker container.

        Returns:
            Container ID

        Raises:
            RuntimeError: If container creation fails
        """
        # Check if container already exists
        existing_id = self._get_container_id()
        if existing_id:
            logger.info(f"Container '{self.container_name}' already exists, removing...")
            self.stop_and_remove_container()

        logger.info(f"Creating PostgreSQL container '{self.container_name}'...")

        try:
            # Create and start container
            result = subprocess.run(
                [
                    "docker",
                    "run",
                    "--name",
                    self.container_name,
                    "-e",
                    f"POSTGRES_DB={self.database}",
                    "-e",
                    f"POSTGRES_USER={self.user}",
                    "-e",
                    f"POSTGRES_PASSWORD={self.password}",
                    "-p",
                    f"{self.port}:5432",
                    "-d",  # Detached mode
                    "postgres:16-alpine",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
            )

            container_id = result.stdout.strip()
            logger.info(f"Container created: {container_id[:12]}")
            return container_id

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to create container: {e.stderr}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Container creation timed out")

    def wait_for_ready(self, timeout: int = 30) -> bool:
        """Wait for PostgreSQL to be ready to accept connections.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if ready, False if timeout
        """
        logger.info("Waiting for PostgreSQL to be ready...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # Use pg_isready to check if PostgreSQL is accepting connections
                result = subprocess.run(
                    [
                        "docker",
                        "exec",
                        self.container_name,
                        "pg_isready",
                        "-U",
                        self.user,
                        "-d",
                        self.database,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if result.returncode == 0:
                    # PostgreSQL is accepting connections, but we need to verify
                    # the database is actually ready by attempting a simple query
                    try:
                        test_result = subprocess.run(
                            [
                                "docker",
                                "exec",
                                self.container_name,
                                "psql",
                                "-U",
                                self.user,
                                "-d",
                                self.database,
                                "-c",
                                "SELECT 1;",
                            ],
                            capture_output=True,
                            text=True,
                            timeout=5,
                        )

                        if test_result.returncode == 0:
                            elapsed = time.time() - start_time
                            logger.info(f"PostgreSQL ready after {elapsed:.1f}s")
                            return True
                    except (subprocess.SubprocessError, subprocess.TimeoutExpired):
                        pass

            except (subprocess.SubprocessError, subprocess.TimeoutExpired):
                pass

            time.sleep(1)

        logger.error(f"PostgreSQL not ready after {timeout}s")
        return False

    def stop_and_remove_container(self) -> None:
        """Stop and remove the Docker container."""
        container_id = self._get_container_id()
        if not container_id:
            logger.debug(f"Container '{self.container_name}' does not exist")
            return

        logger.info(f"Stopping container '{self.container_name}'...")

        try:
            # Stop container
            subprocess.run(
                ["docker", "stop", self.container_name],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )

            # Remove container
            subprocess.run(
                ["docker", "rm", self.container_name],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )

            logger.info(f"Container '{self.container_name}' removed")

        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to remove container: {e.stderr}")
        except subprocess.TimeoutExpired:
            logger.warning("Container removal timed out")

    def get_connection_info(self) -> Dict[str, str]:
        """Get PostgreSQL connection information.

        Returns:
            Dictionary with connection parameters
        """
        return {
            "host": "localhost",
            "port": str(self.port),
            "database": self.database,
            "user": self.user,
            "password": self.password,
        }

    def _get_container_id(self) -> Optional[str]:
        """Get container ID if it exists.

        Returns:
            Container ID or None if not found
        """
        try:
            result = subprocess.run(
                [
                    "docker",
                    "ps",
                    "-a",
                    "--filter",
                    f"name=^{self.container_name}$",
                    "--format",
                    "{{.ID}}",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )

            container_id = result.stdout.strip()
            return container_id if container_id else None

        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            return None
