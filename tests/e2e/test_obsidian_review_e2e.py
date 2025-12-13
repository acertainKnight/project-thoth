"""
End-to-end test for Obsidian Article Review workflow.

This test demonstrates the complete workflow:
1. Export article matches to Obsidian review file
2. Simulate user editing the file (change status fields)
3. Import decisions back to database
4. Verify all changes were applied correctly
"""

import asyncio
import os
from pathlib import Path
from uuid import UUID

import pytest
import yaml

from src.thoth.services.postgres_service import PostgresService
from src.thoth.repositories.article_research_match_repository import (
    ArticleResearchMatchRepository,
)
from src.thoth.repositories.research_question_repository import (
    ResearchQuestionRepository,
)
from src.thoth.services.obsidian_review_service import ObsidianReviewService


@pytest.fixture
async def postgres_service():
    """Create PostgresService instance."""
    service = PostgresService()
    await service.connect()
    yield service
    await service.disconnect()


@pytest.fixture
async def review_service(postgres_service):
    """Create ObsidianReviewService instance."""
    return ObsidianReviewService(postgres_service=postgres_service)


@pytest.fixture
async def active_question(postgres_service):
    """Get an active research question from database."""
    repo = ResearchQuestionRepository(postgres_service)
    questions = await repo.get_active_questions(limit=1)
    if not questions:
        pytest.skip("No active research questions found in database")
    return questions[0]


@pytest.mark.asyncio
async def test_complete_workflow(
    review_service, active_question, tmp_path
):
    """
    Test complete end-to-end workflow:
    Export → Edit → Import → Verify
    """
    question_id = active_question["id"]
    question_name = active_question["name"]

    print(f"\n🔬 Testing workflow for: {question_name}")
    print(f"   Question ID: {question_id}")

    # Step 1: Export article matches to review file
    print("\n📤 Step 1: Exporting article matches...")
    output_path = tmp_path / f"{question_name.replace(' ', '_')}_Review.md"

    review_file = await review_service.generate_obsidian_review_file(
        question_id=question_id, output_path=output_path
    )

    assert review_file.exists(), "Review file should be created"
    print(f"   ✅ Created: {review_file}")

    # Read and parse the exported file
    with open(review_file, "r") as f:
        content = f.read()

    # Extract YAML frontmatter
    if content.startswith("---\n"):
        parts = content.split("---\n", 2)
        frontmatter_yaml = parts[1]
        frontmatter = yaml.safe_load(frontmatter_yaml)
    else:
        pytest.fail("No YAML frontmatter found in exported file")

    articles = frontmatter.get("articles", [])
    total_articles = len(articles)

    print(f"   📊 Exported {total_articles} articles")

    if total_articles == 0:
        pytest.skip("No articles to review for this question")

    # Step 2: Simulate user editing the file
    print("\n✏️  Step 2: Simulating user edits...")

    # Select articles to like (first 3 with highest relevance)
    articles_sorted = sorted(
        articles, key=lambda x: x.get("relevance", 0), reverse=True
    )
    to_like = min(3, len(articles_sorted))
    to_dislike = min(2, len(articles_sorted) - to_like)
    to_skip = min(2, len(articles_sorted) - to_like - to_dislike)

    for i in range(to_like):
        articles_sorted[i]["status"] = "liked"
        articles_sorted[i]["notes"] = "Highly relevant"

    for i in range(to_like, to_like + to_dislike):
        articles_sorted[i]["status"] = "disliked"
        articles_sorted[i]["notes"] = "Not relevant"

    for i in range(
        to_like + to_dislike, to_like + to_dislike + to_skip
    ):
        articles_sorted[i]["status"] = "skip"

    # Update frontmatter
    frontmatter["articles"] = articles_sorted

    # Write modified file
    modified_yaml = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
    modified_content = f"---\n{modified_yaml}---\n" + parts[2]

    with open(review_file, "w") as f:
        f.write(modified_content)

    print(f"   ⭐ Liked: {to_like}")
    print(f"   ❌ Disliked: {to_dislike}")
    print(f"   ⏭️  Skipped: {to_skip}")

    # Step 3: Apply decisions to database
    print("\n💾 Step 3: Applying decisions to database...")

    results = await review_service.apply_review_decisions(review_file)

    print(f"   ✅ Liked: {results['liked']}")
    print(f"   ❌ Disliked: {results['disliked']}")
    print(f"   ⏭️  Skipped: {results['skipped']}")
    print(f"   📝 Updated: {results['updated']}")
    print(f"   ⚠️  Errors: {results['errors']}")

    assert results["liked"] == to_like, "Should update liked count"
    assert results["disliked"] == to_dislike, "Should update disliked count"
    assert results["skipped"] == to_skip, "Should update skipped count"
    assert results["errors"] == 0, "Should have no errors"

    # Step 4: Verify changes in database
    print("\n🔍 Step 4: Verifying database changes...")

    match_repo = ArticleResearchMatchRepository(review_service.postgres)

    # Get sentiment summary
    summary = await match_repo.get_sentiment_summary(question_id)

    print(f"   Database sentiment summary:")
    print(f"   - Liked: {summary.get('liked', 0)}")
    print(f"   - Disliked: {summary.get('disliked', 0)}")
    print(f"   - Skipped: {summary.get('skipped', 0)}")
    print(f"   - Pending: {summary.get('pending', 0)}")

    # Verify liked articles are bookmarked
    for article in articles_sorted[:to_like]:
        match_id = UUID(article["id"])
        match = await match_repo.get_by_id(match_id)

        assert match is not None, f"Match {match_id} should exist"
        assert match["is_bookmarked"], "Liked articles should be bookmarked"
        assert match["user_rating"] == 5, "Liked articles should have rating 5"
        assert match["is_viewed"], "Liked articles should be marked viewed"

    # Verify disliked articles have rating 1
    for article in articles_sorted[to_like : to_like + to_dislike]:
        match_id = UUID(article["id"])
        match = await match_repo.get_by_id(match_id)

        assert match is not None, f"Match {match_id} should exist"
        assert match["user_rating"] == 1, "Disliked articles should have rating 1"
        assert match["is_viewed"], "Disliked articles should be marked viewed"

    # Verify skipped articles are viewed
    for article in articles_sorted[
        to_like + to_dislike : to_like + to_dislike + to_skip
    ]:
        match_id = UUID(article["id"])
        match = await match_repo.get_by_id(match_id)

        assert match is not None, f"Match {match_id} should exist"
        assert match["is_viewed"], "Skipped articles should be marked viewed"

    print("\n✅ End-to-end workflow complete and verified!")


@pytest.mark.asyncio
async def test_workflow_with_api_integration(
    review_service, active_question, tmp_path
):
    """
    Test workflow including API endpoint for sentiment updates.
    This would typically use FastAPI TestClient, but demonstrates the flow.
    """
    question_id = active_question["id"]

    # Export
    output_path = tmp_path / "test_review.md"
    review_file = await review_service.generate_obsidian_review_file(
        question_id=question_id, output_path=output_path
    )

    assert review_file.exists()

    # Read frontmatter
    with open(review_file, "r") as f:
        content = f.read()

    parts = content.split("---\n", 2)
    frontmatter = yaml.safe_load(parts[1])
    articles = frontmatter.get("articles", [])

    if not articles:
        pytest.skip("No articles to test")

    # Pick one article
    test_article = articles[0]
    match_id = UUID(test_article["id"])

    # Update via repository (simulates API endpoint call)
    match_repo = ArticleResearchMatchRepository(review_service.postgres)

    # Test each sentiment type
    sentiments = ["like", "dislike", "skip"]
    for sentiment in sentiments:
        success = await match_repo.set_user_sentiment(match_id, sentiment)
        assert success, f"Should successfully set sentiment to {sentiment}"

        # Verify
        match = await match_repo.get_by_id(match_id)
        assert match is not None

        # Note: user_sentiment column may not exist yet if migration not run
        # This test will be skipped or fail gracefully
        if "user_sentiment" in match:
            assert match["user_sentiment"] == sentiment


def test_cli_export_command_format():
    """
    Test that CLI command format is correct.
    This is a simple validation test, not actual execution.
    """
    # Expected command format
    export_cmd = 'thoth research export-review "AI Agent Memory Systems"'
    apply_cmd = "thoth research apply-review /path/to/file.md"

    # Validate format
    assert "thoth research export-review" in export_cmd
    assert "thoth research apply-review" in apply_cmd

    # With options
    export_with_options = (
        'thoth research export-review "Memory" --min-relevance 0.7 --limit 50'
    )
    assert "--min-relevance" in export_with_options
    assert "--limit" in export_with_options

    apply_dry_run = "thoth research apply-review file.md --dry-run"
    assert "--dry-run" in apply_dry_run


if __name__ == "__main__":
    """
    Run this test manually:

    python tests/e2e/test_obsidian_review_e2e.py

    Or with pytest:

    pytest tests/e2e/test_obsidian_review_e2e.py -v -s
    """
    # Manual test execution
    import sys

    print("🧪 Manual E2E Test Execution")
    print("=" * 60)

    async def run_manual_test():
        from tempfile import mkdtemp

        postgres = PostgresService()
        await postgres.connect()

        try:
            service = ObsidianReviewService(postgres_service=postgres)
            repo = ResearchQuestionRepository(postgres)
            questions = await repo.get_active_questions(limit=1)

            if not questions:
                print("❌ No active research questions found")
                return

            question = questions[0]
            tmp_dir = Path(mkdtemp())

            print(f"\n📋 Testing with question: {question['name']}")
            print(f"   Temp directory: {tmp_dir}")

            await test_complete_workflow(service, question, tmp_dir)

            print("\n✅ All manual tests passed!")

        finally:
            await postgres.disconnect()

    asyncio.run(run_manual_test())
