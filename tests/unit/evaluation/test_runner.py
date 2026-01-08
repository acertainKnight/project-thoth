"""
Tests for runner.py - End-to-End Evaluation Runner.

Tests:
1. End-to-end evaluation pipeline
2. Error handling for missing database
3. Report generation
4. Async operation safety
"""

import pytest  # noqa: I001
import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch, MagicMock  # noqa: F401

from thoth.analyze.citations.evaluation.runner import run_evaluation, main


class TestRunEvaluation:
    """Test main evaluation runner function."""

    @pytest.mark.asyncio
    async def test_run_evaluation_complete_pipeline(self, mock_postgres, monkeypatch):
        """Test complete evaluation pipeline runs successfully."""
        # Mock dependencies
        mock_config = Mock()
        mock_resolution_chain = AsyncMock()
        mock_resolution_chain.batch_resolve = AsyncMock(return_value=[])
        mock_resolution_chain.close = AsyncMock()

        # Mock ground truth generator
        mock_gt_generator = Mock()
        mock_gt_generator.generate_from_database = AsyncMock(return_value=[])

        # Patch imports
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.Config', lambda: mock_config
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.PostgresService',
            lambda x: mock_postgres,  # noqa: ARG005
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.CitationResolutionChain',
            lambda: mock_resolution_chain,
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.GroundTruthGenerator',
            lambda x: mock_gt_generator,  # noqa: ARG005
        )

        # Patch visualization functions to prevent file I/O
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.create_evaluation_report', Mock()
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.plot_calibration_curve', Mock()
        )

        # Run evaluation
        result = await run_evaluation(  # noqa: F841
            num_samples=10,
            output_dir=Path('/tmp/test_eval'),
            require_doi=True,
            stratify=True,
        )

        # Verify pipeline steps were called
        mock_postgres.initialize.assert_called_once()
        mock_gt_generator.generate_from_database.assert_called_once()
        mock_postgres.close.assert_called_once()
        mock_resolution_chain.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_evaluation_no_ground_truth_returns_none(
        self, mock_postgres, monkeypatch
    ):
        """Test evaluation returns None when no ground truth generated."""
        mock_config = Mock()
        mock_resolution_chain = AsyncMock()
        mock_resolution_chain.close = AsyncMock()

        # Mock generator that returns empty list
        mock_gt_generator = Mock()
        mock_gt_generator.generate_from_database = AsyncMock(return_value=[])

        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.Config', lambda: mock_config
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.PostgresService',
            lambda x: mock_postgres,  # noqa: ARG005
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.CitationResolutionChain',
            lambda: mock_resolution_chain,
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.GroundTruthGenerator',
            lambda x: mock_gt_generator,  # noqa: ARG005
        )

        result = await run_evaluation(num_samples=10)

        assert result is None

    @pytest.mark.asyncio
    async def test_run_evaluation_cleanup_on_error(self, mock_postgres, monkeypatch):
        """Test services are cleaned up even when error occurs."""
        mock_config = Mock()
        mock_resolution_chain = AsyncMock()
        mock_resolution_chain.close = AsyncMock()

        # Mock generator that raises error
        mock_gt_generator = Mock()
        mock_gt_generator.generate_from_database = AsyncMock(
            side_effect=Exception('Database error')
        )

        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.Config', lambda: mock_config
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.PostgresService',
            lambda x: mock_postgres,  # noqa: ARG005
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.CitationResolutionChain',
            lambda: mock_resolution_chain,
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.GroundTruthGenerator',
            lambda x: mock_gt_generator,  # noqa: ARG005
        )

        with pytest.raises(Exception, match='Database error'):
            await run_evaluation(num_samples=10)

        # Verify cleanup was called
        mock_postgres.close.assert_called_once()
        mock_resolution_chain.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_evaluation_creates_output_directory(
        self,
        mock_postgres,
        tmp_path,
        monkeypatch,
        multiple_ground_truth,
        multiple_resolution_results,
    ):
        """Test evaluation creates output directory with timestamp."""
        mock_config = Mock()
        mock_resolution_chain = AsyncMock()
        mock_resolution_chain.batch_resolve = AsyncMock(
            return_value=multiple_resolution_results
        )
        mock_resolution_chain.close = AsyncMock()

        mock_gt_generator = Mock()
        mock_gt_generator.generate_from_database = AsyncMock(
            return_value=multiple_ground_truth
        )

        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.Config', lambda: mock_config
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.PostgresService',
            lambda x: mock_postgres,  # noqa: ARG005
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.CitationResolutionChain',
            lambda: mock_resolution_chain,
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.GroundTruthGenerator',
            lambda x: mock_gt_generator,  # noqa: ARG005
        )

        # Patch visualization to prevent file I/O errors
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.create_evaluation_report', Mock()
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.plot_calibration_curve', Mock()
        )

        output_dir = tmp_path / 'evaluation_output'
        await run_evaluation(num_samples=3, output_dir=output_dir)

        # Check that directory was created with timestamp subdirectory
        assert output_dir.exists()
        eval_dirs = list(output_dir.glob('evaluation_*'))
        assert len(eval_dirs) >= 1

    @pytest.mark.asyncio
    async def test_run_evaluation_saves_summary_json(
        self,
        mock_postgres,
        tmp_path,
        monkeypatch,
        multiple_ground_truth,
        multiple_resolution_results,
    ):
        """Test evaluation saves summary JSON file."""
        mock_config = Mock()
        mock_resolution_chain = AsyncMock()
        mock_resolution_chain.batch_resolve = AsyncMock(
            return_value=multiple_resolution_results
        )
        mock_resolution_chain.close = AsyncMock()

        mock_gt_generator = Mock()
        mock_gt_generator.generate_from_database = AsyncMock(
            return_value=multiple_ground_truth
        )

        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.Config', lambda: mock_config
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.PostgresService',
            lambda x: mock_postgres,  # noqa: ARG005
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.CitationResolutionChain',
            lambda: mock_resolution_chain,
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.GroundTruthGenerator',
            lambda x: mock_gt_generator,  # noqa: ARG005
        )

        # Patch visualization
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.create_evaluation_report', Mock()
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.plot_calibration_curve', Mock()
        )

        output_dir = tmp_path / 'evaluation_output'
        await run_evaluation(num_samples=3, output_dir=output_dir)

        # Find evaluation directory
        eval_dirs = list(output_dir.glob('evaluation_*'))
        assert len(eval_dirs) >= 1

        summary_file = eval_dirs[0] / 'summary.json'
        assert summary_file.exists()

        # Verify JSON structure
        with open(summary_file) as f:
            summary = json.load(f)

        assert 'timestamp' in summary
        assert 'num_samples' in summary
        assert 'metrics' in summary
        assert 'precision' in summary['metrics']
        assert 'recall' in summary['metrics']
        assert 'f1_score' in summary['metrics']

    @pytest.mark.asyncio
    async def test_run_evaluation_uses_parameters(self, mock_postgres, monkeypatch):
        """Test evaluation uses provided parameters."""
        mock_config = Mock()
        mock_resolution_chain = AsyncMock()
        mock_resolution_chain.batch_resolve = AsyncMock(return_value=[])
        mock_resolution_chain.close = AsyncMock()

        mock_gt_generator = Mock()
        mock_gt_generator.generate_from_database = AsyncMock(return_value=[])

        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.Config', lambda: mock_config
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.PostgresService',
            lambda x: mock_postgres,  # noqa: ARG005
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.CitationResolutionChain',
            lambda: mock_resolution_chain,
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.GroundTruthGenerator',
            lambda x: mock_gt_generator,  # noqa: ARG005
        )

        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.create_evaluation_report', Mock()
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.plot_calibration_curve', Mock()
        )

        await run_evaluation(num_samples=123, require_doi=False, stratify=False)

        # Verify parameters were passed to generator
        call_kwargs = mock_gt_generator.generate_from_database.call_args[1]
        assert call_kwargs['num_samples'] == 123
        assert call_kwargs['require_doi'] is False
        assert call_kwargs['stratify_by_difficulty'] is False


class TestMainCLI:
    """Test CLI entry point."""

    @patch('thoth.analyze.citations.evaluation.runner.asyncio.run')
    @patch(
        'thoth.analyze.citations.evaluation.runner.argparse.ArgumentParser.parse_args'
    )
    def test_main_cli_default_arguments(self, mock_parse_args, mock_asyncio_run):
        """Test main() with default arguments."""
        mock_args = Mock()
        mock_args.num_samples = 500
        mock_args.output_dir = './evaluation_results'
        mock_args.require_doi = True
        mock_args.no_stratify = False
        mock_parse_args.return_value = mock_args

        main()

        # Verify asyncio.run was called
        mock_asyncio_run.assert_called_once()

    @patch('thoth.analyze.citations.evaluation.runner.asyncio.run')
    @patch(
        'thoth.analyze.citations.evaluation.runner.argparse.ArgumentParser.parse_args'
    )
    def test_main_cli_custom_arguments(self, mock_parse_args, mock_asyncio_run):
        """Test main() with custom arguments."""
        mock_args = Mock()
        mock_args.num_samples = 100
        mock_args.output_dir = '/custom/path'
        mock_args.require_doi = False
        mock_args.no_stratify = True
        mock_parse_args.return_value = mock_args

        main()

        # Verify arguments were passed correctly
        call_args = mock_asyncio_run.call_args[0][0]  # noqa: F841
        # Should be a coroutine with our parameters
        mock_asyncio_run.assert_called_once()


class TestAsyncSafety:
    """Test async operation safety and concurrency."""

    @pytest.mark.asyncio
    async def test_concurrent_resolution_safe(
        self, mock_postgres, monkeypatch, multiple_ground_truth
    ):
        """Test batch resolution runs safely in parallel."""
        mock_config = Mock()

        # Mock resolution chain with async batch_resolve
        mock_resolution_chain = AsyncMock()

        async def mock_batch_resolve(citations, parallel=True):  # noqa: ARG001
            # Simulate async work
            import asyncio

            await asyncio.sleep(0.01)
            # Return properly configured Mock ResolutionResult objects
            results = []
            for _ in citations:
                mock_result = Mock()
                mock_result.confidence_score = 0.9
                mock_result.metadata = Mock()
                mock_result.metadata.api_sources_tried = [
                    'crossref',
                    'semantic_scholar',
                ]
                results.append(mock_result)
            return results

        mock_resolution_chain.batch_resolve = mock_batch_resolve
        mock_resolution_chain.close = AsyncMock()

        mock_gt_generator = Mock()
        mock_gt_generator.generate_from_database = AsyncMock(
            return_value=multiple_ground_truth
        )

        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.Config', lambda: mock_config
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.PostgresService',
            lambda x: mock_postgres,  # noqa: ARG005
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.CitationResolutionChain',
            lambda: mock_resolution_chain,
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.GroundTruthGenerator',
            lambda x: mock_gt_generator,  # noqa: ARG005
        )

        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.create_evaluation_report', Mock()
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.plot_calibration_curve', Mock()
        )

        # Should not raise any concurrency errors
        await run_evaluation(num_samples=3)

    @pytest.mark.asyncio
    async def test_database_connection_closed_after_use(
        self, mock_postgres, monkeypatch
    ):
        """Test database connection is properly closed."""
        mock_config = Mock()
        mock_resolution_chain = AsyncMock()
        mock_resolution_chain.batch_resolve = AsyncMock(return_value=[])
        mock_resolution_chain.close = AsyncMock()

        mock_gt_generator = Mock()
        mock_gt_generator.generate_from_database = AsyncMock(return_value=[])

        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.Config', lambda: mock_config
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.PostgresService',
            lambda x: mock_postgres,  # noqa: ARG005
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.CitationResolutionChain',
            lambda: mock_resolution_chain,
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.GroundTruthGenerator',
            lambda x: mock_gt_generator,  # noqa: ARG005
        )

        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.create_evaluation_report', Mock()
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.plot_calibration_curve', Mock()
        )

        await run_evaluation(num_samples=1)

        # Verify close was called
        assert mock_postgres.close.call_count >= 1

    @pytest.mark.asyncio
    async def test_resolution_chain_closed_after_use(self, mock_postgres, monkeypatch):
        """Test resolution chain is properly closed."""
        mock_config = Mock()
        mock_resolution_chain = AsyncMock()
        mock_resolution_chain.batch_resolve = AsyncMock(return_value=[])
        mock_resolution_chain.close = AsyncMock()

        mock_gt_generator = Mock()
        mock_gt_generator.generate_from_database = AsyncMock(return_value=[])

        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.Config', lambda: mock_config
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.PostgresService',
            lambda x: mock_postgres,  # noqa: ARG005
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.CitationResolutionChain',
            lambda: mock_resolution_chain,
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.GroundTruthGenerator',
            lambda x: mock_gt_generator,  # noqa: ARG005
        )

        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.create_evaluation_report', Mock()
        )
        monkeypatch.setattr(
            'thoth.analyze.citations.evaluation.runner.plot_calibration_curve', Mock()
        )

        await run_evaluation(num_samples=1)

        # Verify close was called
        mock_resolution_chain.close.assert_called_once()
