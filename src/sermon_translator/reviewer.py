"""Auto-review and correction of translations."""

import json
import re
from dataclasses import dataclass

from openai import OpenAI

from .config import (
    DEFAULT_MODEL,
    MAX_REVIEW_ITERATIONS,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    REVIEW_SYSTEM_PROMPT,
    REVIEW_TEMPERATURE,
)


@dataclass
class ReviewIssue:
    """An issue found during review."""
    paragraph: int
    original_text: str
    issue_type: str
    suggestion: str


@dataclass
class ReviewResult:
    """Result of a review iteration."""
    approved: bool
    issues: list[ReviewIssue]
    corrected_translation: str | None


class Reviewer:
    """Reviews and corrects translations."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.client = OpenAI(
            api_key=api_key or OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
        )
        self.model = model or DEFAULT_MODEL

    def review_translation(
        self,
        original_text: str,
        translated_text: str,
        verse_table: str = "",
        progress_callback=None,
    ) -> tuple[str, list[ReviewIssue]]:
        """
        Review and potentially correct a translation.

        Args:
            original_text: Original English text with [P1], [P2] markers
            translated_text: Translated Chinese text with [P1], [P2] markers
            verse_table: Bible verse reference table
            progress_callback: Optional callback for progress updates

        Returns:
            Tuple of (final translation, list of all issues found)
        """
        current_translation = translated_text
        all_issues = []

        for iteration in range(MAX_REVIEW_ITERATIONS):
            if progress_callback:
                progress_callback(iteration + 1, MAX_REVIEW_ITERATIONS)

            result = self._review_iteration(
                original_text,
                current_translation,
                verse_table,
            )

            if result.approved:
                return current_translation, all_issues

            all_issues.extend(result.issues)

            if result.corrected_translation:
                current_translation = result.corrected_translation
            else:
                # No correction provided, stop iterations
                break

        return current_translation, all_issues

    def _review_iteration(
        self,
        original: str,
        translated: str,
        verse_table: str,
    ) -> ReviewResult:
        """
        Perform one review iteration.

        Args:
            original: Original English text
            translated: Current translated text
            verse_table: Bible verse reference table

        Returns:
            ReviewResult with approval status and any corrections
        """
        prompt = REVIEW_SYSTEM_PROMPT.format(
            original=original,
            translated=translated,
            verse_table=verse_table if verse_table else "[No Bible verse references]",
        )

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=REVIEW_TEMPERATURE,
            messages=[
                {"role": "system", "content": "You are a translation quality reviewer."},
                {"role": "user", "content": prompt},
            ],
        )

        content = response.choices[0].message.content or ""

        return self._parse_review_response(content)

    def _parse_review_response(self, response: str) -> ReviewResult:
        """
        Parse the review response.

        Args:
            response: The model's response

        Returns:
            ReviewResult with parsed information
        """
        # Check for approval
        if response.strip().upper() == "APPROVED":
            return ReviewResult(approved=True, issues=[], corrected_translation=None)

        # Try to parse as JSON
        try:
            # Find JSON in the response
            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())

                issues = []
                for issue_data in data.get("issues", []):
                    original_text = issue_data.get("original_text", "")
                    suggestion = issue_data.get("suggestion", "")
                    # Skip false positives where suggestion is identical to original
                    if original_text.strip() == suggestion.strip():
                        continue
                    issues.append(ReviewIssue(
                        paragraph=issue_data.get("paragraph", 0),
                        original_text=original_text,
                        issue_type=issue_data.get("issue_type", "unknown"),
                        suggestion=suggestion,
                    ))

                # If all issues were filtered out, treat as approved
                if not issues:
                    return ReviewResult(approved=True, issues=[], corrected_translation=None)

                return ReviewResult(
                    approved=False,
                    issues=issues,
                    corrected_translation=data.get("corrected_translation"),
                )
        except json.JSONDecodeError:
            pass

        # If we can't parse the response, treat as approved (no clear issues)
        return ReviewResult(approved=True, issues=[], corrected_translation=None)


def format_review_report(issues: list[ReviewIssue]) -> str:
    """
    Format review issues as a human-readable report.

    Args:
        issues: List of review issues

    Returns:
        Formatted report string
    """
    if not issues:
        return "No issues found during review."

    lines = [f"Review found {len(issues)} issue(s):", ""]

    for i, issue in enumerate(issues, 1):
        lines.append(f"{i}. Paragraph {issue.paragraph} - {issue.issue_type}")
        lines.append(f"   Original: {issue.original_text}")
        lines.append(f"   Suggestion: {issue.suggestion}")
        lines.append("")

    return "\n".join(lines)
