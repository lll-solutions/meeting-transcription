from abc import ABC, abstractmethod
from typing import Dict, Any, List
from pathlib import Path


class BaseFormatter(ABC):
    """
    Abstract base class for formatting LLM output into final documents.

    Different content types produce different output formats:
    - Educational: Study guide (Markdown/PDF)
    - Therapy: SOAP note (clinical text format), Action plan (client-facing)

    This interface enables domain-specific output formatting while
    maintaining consistent pipeline structure.
    """

    @abstractmethod
    def format_output(
        self,
        summary_data: Dict[str, Any],
        output_dir: Path
    ) -> Dict[str, str]:
        """
        Format LLM output into final documents.

        Args:
            summary_data: Processed summary from LLM containing:
                - 'metadata': ChunkMetadata
                - 'overall_summary': Dict from LLM
                - 'action_items': Dict from LLM
                - 'chunk_analyses': List of chunk analyses
            output_dir: Directory to write output files

        Returns:
            Dict mapping output names to file paths
            Example: {
                'study_guide': '/path/to/study_guide.md',
                'pdf': '/path/to/study_guide.pdf'
            }
        """
        pass

    @abstractmethod
    def get_output_types(self) -> List[str]:
        """
        Return list of output types this formatter produces.

        Returns:
            List of output type names
            Example: ['study_guide', 'pdf'] or ['soap_note', 'action_plan']
        """
        pass
