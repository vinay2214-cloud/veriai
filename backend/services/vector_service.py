import faiss
import os
import logging
import shutil
import tempfile

from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class VectorStore:
    """
    Minimal FAISS vector store implementation for VeriAI.
    Includes:
    - safe initialization
    - corruption recovery
    - atomic saves
    - graceful startup support
    """

    def __init__(self, index_dir: str):
        self.index_dir = index_dir
        self.index_path = os.path.join(index_dir, "index.faiss")

        # Match your embedding dimension
        self.dimension = 1536

        self.index: Optional[faiss.Index] = None
        self._is_initialized = False

        os.makedirs(self.index_dir, exist_ok=True)

    def initialize(self) -> None:
        """
        Initialize FAISS index safely.
        """

        try:
            # Load existing index
            if os.path.exists(self.index_path):
                try:
                    self.index = faiss.read_index(self.index_path)
                    self._is_initialized = True
                    self._log_loaded()
                    return

                except Exception as e:
                    logger.warning(f"FAISS corruption detected: {str(e)}")
                    self._recover_from_corruption()

            # Create new empty index
            self._create_empty_index()

        except Exception as e:
            logger.error(f"FAISS initialization failed: {str(e)}")
            raise

    def _recover_from_corruption(self) -> None:
        """
        Backup corrupted index and recreate.
        """

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        backup_path = (
            f"{self.index_path}.corrupted_{timestamp}"
        )

        try:
            shutil.move(self.index_path, backup_path)

            logger.warning(
                f"Backed up corrupted index to {backup_path}"
            )

        except Exception as e:
            logger.error(
                f"Failed to backup corrupted index: {str(e)}"
            )

        self._create_empty_index()

    def _create_empty_index(self) -> None:
        """
        Create fresh empty FAISS index.
        """

        self.index = faiss.IndexFlatL2(self.dimension)
        self._is_initialized = True

        logger.info(
            f"Created new FAISS index at {self.index_path}"
        )

    def _log_loaded(self) -> None:
        """
        Log successful index load.
        """

        vec_count = self.index.ntotal if self.index else 0

        logger.info(
            f"Loaded FAISS index with {vec_count} vectors"
        )

    def save_index(self) -> bool:
        """
        Save index safely using atomic file replacement.
        """

        if not self.index or not self._is_initialized:
            logger.warning(
                "Attempted to save uninitialized index"
            )
            return False

        temp_path = None

        try:
            temp_fd, temp_path = tempfile.mkstemp(
                dir=self.index_dir
            )

            os.close(temp_fd)

            # Write temporary index
            faiss.write_index(self.index, temp_path)

            # Atomic replace
            os.replace(temp_path, self.index_path)

            logger.info(
                f"Saved FAISS index with {self.index.ntotal} vectors"
            )

            return True

        except Exception as e:
            logger.error(f"Failed to save index: {str(e)}")

            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

            return False