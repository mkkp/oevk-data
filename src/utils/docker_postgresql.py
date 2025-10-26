"""Docker PostgreSQL container management utilities."""

import subprocess
import time
import platform as platform_module
import socket
from typing import Optional, Dict

from src.utils.pipeline_logging import get_logger

logger = get_logger(__name__)


class DockerPostgreSQLManager:
    """Manages Docker PostgreSQL container lifecycle for verification."""

    def __init__(
        self,
        container_name: str = "oevk-verify",
        port: Optional[int] = None,
        database: str = "oevk",
        user: str = "oevk",
        password: str = "oevk",
        use_postgis: bool = True,
    ):
        """Initialize Docker PostgreSQL manager.

        Args:
            container_name: Name for the Docker container
            port: PostgreSQL port (default: auto-find available port)
            database: Database name (default: oevk)
            user: PostgreSQL user (default: oevk)
            password: PostgreSQL password (default: oevk)
            use_postgis: Use PostGIS image instead of standard PostgreSQL (default: True)
        """
        self.container_name = container_name
        self.port = port if port is not None else self._find_available_port()
        self.database = database
        self.user = user
        self.password = password
        self.use_postgis = use_postgis

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

        # Choose Docker image based on PostGIS configuration
        # Use PostGIS 15-3.3 which has multi-arch support (amd64/arm64)
        if self.use_postgis:
            postgres_image = "postgis/postgis:15-3.3"
        else:
            postgres_image = "postgres:16"

        logger.info(f"Creating PostgreSQL container '{self.container_name}' (image: {postgres_image}, port: {self.port})...")

        try:
            # Create and start container (Docker will auto-select correct architecture)
            docker_cmd = [
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
                postgres_image,
            ]

            result = subprocess.run(
                docker_cmd,
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

    def _find_available_port(self, start_port: int = 5433, max_attempts: int = 100) -> int:
        """Find an available port for PostgreSQL.

        Args:
            start_port: Port to start searching from (default: 5433 to avoid conflict with default 5432)
            max_attempts: Maximum number of ports to try

        Returns:
            Available port number

        Raises:
            RuntimeError: If no available port found
        """
        for port in range(start_port, start_port + max_attempts):
            try:
                # Try to bind to the port to check if it's available
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("", port))
                    logger.debug(f"Found available port: {port}")
                    return port
            except OSError:
                # Port is in use, try next one
                continue

        raise RuntimeError(f"No available port found in range {start_port}-{start_port + max_attempts}")
