from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse

from .demo import DEMO_TEXT
from .forms import SourceForm
from .models import Flashcard, Source
from .services import CardGenerationError, generate_cards, validate_cards


def demo_source_text():
    return " ".join(card["source_quote"] for card in DEMO_TEXT)


class SourceFormTests(TestCase):
    def test_valid_form_normalizes_windows_newlines(self):
        text = f"{demo_source_text()}\r\nДополнительное предложение."
        form = SourceForm({"title": "Сети", "text": text})

        self.assertTrue(form.is_valid())
        self.assertNotIn("\r", form.cleaned_data["text"])
        self.assertIn("\n", form.cleaned_data["text"])

    def test_form_rejects_missing_title_and_short_text(self):
        form = SourceForm({"title": "", "text": "Короткий текст"})

        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)
        self.assertIn("text", form.errors)

    def test_form_rejects_title_over_120_characters(self):
        form = SourceForm({"title": "Т" * 121, "text": demo_source_text()})

        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)


class CardValidationTests(TestCase):
    def setUp(self):
        self.text = demo_source_text()
        self.cards = [card.copy() for card in DEMO_TEXT]

    def test_accepts_cards_with_exact_quotes(self):
        self.assertEqual(validate_cards(self.cards, self.text), self.cards)

    def test_rejects_invalid_card_count_and_empty_fields(self):
        with self.assertRaises(CardGenerationError):
            validate_cards(self.cards[:2], self.text)

        cards_with_empty_answer = [card.copy() for card in self.cards]
        cards_with_empty_answer[0]["answer"] = " "
        with self.assertRaises(CardGenerationError):
            validate_cards(cards_with_empty_answer, self.text)

    def test_rejects_nonmatching_quote_and_duplicate_questions(self):
        cards_with_invalid_quote = [card.copy() for card in self.cards]
        cards_with_invalid_quote[0]["source_quote"] += " "
        with self.assertRaises(CardGenerationError):
            validate_cards(cards_with_invalid_quote, self.text)

        cards_with_duplicate_question = [card.copy() for card in self.cards]
        cards_with_duplicate_question[1]["question"] = cards_with_duplicate_question[0]["question"]
        with self.assertRaises(CardGenerationError):
            validate_cards(cards_with_duplicate_question, self.text)


class DemoGenerationTests(TestCase):
    @patch("study.services.get_provider_mode", return_value="demo")
    def test_generate_cards_returns_three_demo_cards(self, get_mode):
        cards = generate_cards(demo_source_text())

        self.assertEqual(len(cards), 3)
        self.assertEqual(cards, DEMO_TEXT)
        self.assertTrue(
            all(card["source_quote"] in demo_source_text() for card in cards)
        )
        get_mode.assert_called_once_with()

    @patch("study.services.get_provider_mode", return_value="unsupported")
    def test_unknown_provider_mode_raises_generation_error(self, get_mode):
        with self.assertRaises(CardGenerationError):
            generate_cards(demo_source_text())


class SourceViewTests(TestCase):
    def setUp(self):
        self.text = demo_source_text()
        self.home_url = reverse("home")

    @patch("study.views.get_provider_mode", return_value="demo")
    def test_home_get_renders_form(self, get_mode):
        response = self.client.get(self.home_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Создать карточки")
        get_mode.assert_called_once_with()

    @patch("study.views.get_provider_mode", return_value="demo")
    def test_invalid_post_renders_errors_and_preserves_input(self, get_mode):
        response = self.client.post(
            self.home_url,
            {"title": "Сети", "text": "Слишком короткий текст"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Слишком короткий текст")
        self.assertContains(response, "50")
        self.assertFalse(Source.objects.exists())
        get_mode.assert_called_once_with()

    @patch("study.views.get_provider_mode", return_value="demo")
    def test_valid_post_saves_source_and_cards_then_redirects(self, get_mode):
        response = self.client.post(
            self.home_url,
            {"title": "Компьютерные сети", "text": self.text},
        )

        source = Source.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            reverse("source_detail", args=[source.pk]),
        )
        self.assertEqual(source.text, self.text)
        self.assertEqual(source.generation_mode, "DEMO")
        self.assertEqual(source.cards.count(), 3)
        self.assertEqual(
            list(source.cards.values_list("position", flat=True)),
            [1, 2, 3],
        )
        get_mode.assert_called_once_with()

    @patch("study.views.get_provider_mode", return_value="demo")
    @patch(
        "study.views.Flashcard.objects.bulk_create",
        side_effect=DatabaseError("simulated database failure"),
    )
    def test_database_error_rolls_back_source_and_renders_error(
        self, bulk_create, get_mode
    ):
        response = self.client.post(
            self.home_url,
            {"title": "Компьютерные сети", "text": self.text},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Не удалось сохранить конспект и карточки")
        self.assertFalse(Source.objects.exists())
        bulk_create.assert_called_once()
        get_mode.assert_called_once_with()

    def test_source_detail_shows_question_and_hides_answer_in_details(self):
        source = Source.objects.create(
            title="Компьютерные сети",
            text=self.text,
            generation_mode="DEMO",
        )
        Flashcard.objects.create(
            source=source,
            position=1,
            question="Что такое IP-адрес?",
            answer="Адрес устройства в сети.",
            source_quote=DEMO_TEXT[0]["source_quote"],
        )

        response = self.client.get(reverse("source_detail", args=[source.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Что такое IP-адрес?")
        self.assertContains(response, "<details>")
        self.assertContains(response, "<summary>Показать ответ</summary>")
        self.assertContains(response, "Адрес устройства в сети.")
        self.assertContains(response, DEMO_TEXT[0]["source_quote"])

    def test_source_detail_returns_404_for_unknown_source(self):
        response = self.client.get(reverse("source_detail", args=[9999]))

        self.assertEqual(response.status_code, 404)
