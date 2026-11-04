from django.test import TestCase
from django.urls import reverse

from .demo import DEMO_TEXT
from .models import Flashcard, Source


class CardEditorWorkflowTests(TestCase):
    def setUp(self):
        self.source_text = " ".join(
            card["source_quote"] for card in DEMO_TEXT
        )
        self.source = Source.objects.create(
            title="Компьютерные сети",
            text=self.source_text,
            generation_mode="DEMO",
        )
        self.card = Flashcard.objects.create(
            source=self.source,
            position=1,
            question="Что такое IP-адрес?",
            answer="Адрес устройства в сети.",
            source_quote=DEMO_TEXT[0]["source_quote"],
            status=Flashcard.Status.REVIEWED,
        )

    def test_edit_page_displays_card_and_original_source(self):
        response = self.client.get(
            reverse("card_edit", args=[self.card.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.source_text)
        self.assertContains(response, "name=\"question\"")
        self.assertContains(response, "name=\"answer\"")
        self.assertContains(response, "name=\"source_quote\"")

    def test_edit_saves_changes_and_resets_review_state(self):
        response = self.client.post(
            reverse("card_edit", args=[self.card.pk]),
            {
                "question": "Что обозначает IP-адрес?",
                "answer": "Адрес устройства в IP-сети.",
                "source_quote": DEMO_TEXT[0]["source_quote"],
            },
        )

        self.card.refresh_from_db()
        self.assertRedirects(
            response,
            reverse("source_detail", args=[self.source.pk]),
        )
        self.assertEqual(self.card.question, "Что обозначает IP-адрес?")
        self.assertEqual(
            self.card.status,
            Flashcard.Status.NEEDS_REVIEW,
        )

    def test_edit_rejects_quote_not_found_in_source(self):
        response = self.client.post(
            reverse("card_edit", args=[self.card.pk]),
            {
                "question": "Изменённый вопрос",
                "answer": "Изменённый ответ.",
                "source_quote": "Этого предложения нет в конспекте.",
            },
        )

        self.card.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "должна присутствовать")
        self.assertEqual(self.card.question, "Что такое IP-адрес?")
        self.assertEqual(self.card.status, Flashcard.Status.REVIEWED)

    def test_delete_confirmation_does_not_delete_until_post(self):
        response = self.client.get(
            reverse("card_delete", args=[self.card.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.card.question)
        self.assertTrue(
            Flashcard.objects.filter(pk=self.card.pk).exists()
        )

    def test_delete_post_removes_card_and_redirects_to_source(self):
        response = self.client.post(
            reverse("card_delete", args=[self.card.pk])
        )

        self.assertRedirects(
            response,
            reverse("source_detail", args=[self.source.pk]),
        )
        self.assertFalse(
            Flashcard.objects.filter(pk=self.card.pk).exists()
        )

    def test_review_verify_and_reset_actions_update_status(self):
        review_url = reverse("card_review", args=[self.card.pk])

        response = self.client.post(review_url, {"action": "reset"})
        self.card.refresh_from_db()
        self.assertRedirects(
            response,
            reverse("source_detail", args=[self.source.pk]),
        )
        self.assertEqual(self.card.status, Flashcard.Status.NEEDS_REVIEW)

        response = self.client.post(review_url, {"action": "verify"})
        self.card.refresh_from_db()
        self.assertRedirects(
            response,
            reverse("source_detail", args=[self.source.pk]),
        )
        self.assertEqual(self.card.status, Flashcard.Status.REVIEWED)

    def test_review_rejects_get_and_unknown_action(self):
        review_url = reverse("card_review", args=[self.card.pk])

        self.assertEqual(self.client.get(review_url).status_code, 405)
        response = self.client.post(review_url, {"action": "invalid"})

        self.assertEqual(response.status_code, 400)
        self.card.refresh_from_db()
        self.assertEqual(self.card.status, Flashcard.Status.REVIEWED)

    def test_status_filters_keep_global_card_counts(self):
        pending_card = Flashcard.objects.create(
            source=self.source,
            position=2,
            question="Что такое DNS?",
            answer="Сопоставляет имя с IP-адресом.",
            source_quote=DEMO_TEXT[1]["source_quote"],
        )
        detail_url = reverse("source_detail", args=[self.source.pk])

        all_response = self.client.get(detail_url, {"status": "all"})
        self.assertEqual(all_response.status_code, 200)
        self.assertEqual(all_response.context["total_cards"], 2)
        self.assertEqual(all_response.context["reviewed_cards"], 1)
        self.assertEqual(all_response.context["remaining_cards"], 1)
        self.assertContains(all_response, self.card.question)
        self.assertContains(all_response, pending_card.question)

        pending_response = self.client.get(
            detail_url,
            {"status": "pending"},
        )
        self.assertEqual(
            list(pending_response.context["cards"]),
            [pending_card],
        )
        self.assertEqual(pending_response.context["total_cards"], 2)
        self.assertEqual(pending_response.context["reviewed_cards"], 1)

        verified_response = self.client.get(
            detail_url,
            {"status": "verified"},
        )
        self.assertEqual(
            list(verified_response.context["cards"]),
            [self.card],
        )
        self.assertEqual(verified_response.context["remaining_cards"], 1)

    def test_empty_filter_shows_link_to_all_cards(self):
        response = self.client.get(
            reverse("source_detail", args=[self.source.pk]),
            {"status": "pending"},
        )

        self.assertContains(response, "В этом фильтре карточек нет.")
        self.assertContains(
            response,
            'href="?status=all">Барлығын көрсету</a>',
        )
