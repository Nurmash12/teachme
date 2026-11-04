from django.db import DatabaseError, transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import FlashcardForm, SourceForm
from .models import Flashcard, Source
from .services import CardGenerationError, generate_cards, get_provider_mode


def home(request):
    mode = get_provider_mode().upper()
    if request.method == "POST":
        form = SourceForm(request.POST)
        if form.is_valid():
            try:
                cards = generate_cards(form.cleaned_data["text"])
            except CardGenerationError as error:
                return render(
                    request,
                    "study/home.html",
                    {"form": form, "generation_error": str(error), "mode": mode},
                )
            try:
                with transaction.atomic():
                    source = Source.objects.create(
                        title=form.cleaned_data["title"],
                        text=form.cleaned_data["text"],
                        generation_mode=mode,
                    )
                    Flashcard.objects.bulk_create(
                        [
                            Flashcard(
                                source=source,
                                position=position,
                                question=card["question"],
                                answer=card["answer"],
                                source_quote=card["source_quote"],
                            )
                            for position, card in enumerate(cards, start=1)
                        ]
                    )
            except DatabaseError:
                return render(
                    request,
                    "study/home.html",
                    {
                        "form": form,
                        "generation_error": (
                            "Не удалось сохранить конспект и карточки. "
                            "Попробуйте ещё раз."
                        ),
                        "mode": mode,
                    },
                )
            return redirect("source_detail", pk=source.pk)
    else:
        form = SourceForm()

    return render(request, "study/home.html", {"form": form, "mode": mode})


def source_detail(request, pk):
    source = get_object_or_404(Source, pk=pk)
    all_cards = source.cards.all()
    total_cards = all_cards.count()
    reviewed_cards = all_cards.filter(status=Flashcard.Status.REVIEWED).count()
    remaining_cards = total_cards - reviewed_cards
    status = request.GET.get("status", "all")

    if status == "pending":
        cards = all_cards.filter(status=Flashcard.Status.NEEDS_REVIEW)
    elif status == "verified":
        cards = all_cards.filter(status=Flashcard.Status.REVIEWED)
    else:
        status = "all"
        cards = all_cards

    return render(
        request,
        "study/source_detail.html",
        {
            "source": source,
            "cards": cards,
            "status_filter": status,
            "total_cards": total_cards,
            "reviewed_cards": reviewed_cards,
            "remaining_cards": remaining_cards,
        },
    )


def card_edit(request, pk):
    card = get_object_or_404(Flashcard.objects.select_related("source"), pk=pk)
    if request.method == "POST":
        form = FlashcardForm(
            request.POST,
            instance=card,
            source_text=card.source.text,
        )
        if form.is_valid():
            card = form.save(commit=False)
            card.status = Flashcard.Status.NEEDS_REVIEW
            card.save()
            return redirect("source_detail", pk=card.source_id)
    else:
        form = FlashcardForm(instance=card, source_text=card.source.text)

    return render(
        request,
        "study/card_form.html",
        {"form": form, "card": card, "source": card.source},
    )


@require_POST
def card_review(request, pk):
    card = get_object_or_404(Flashcard, pk=pk)
    action = request.POST.get("action")
    if action == "verify":
        card.status = Flashcard.Status.REVIEWED
    elif action == "reset":
        card.status = Flashcard.Status.NEEDS_REVIEW
    else:
        return HttpResponseBadRequest("Недопустимое действие проверки карточки.")

    card.save(update_fields=["status"])
    return redirect("source_detail", pk=card.source_id)


def card_delete(request, pk):
    card = get_object_or_404(Flashcard.objects.select_related("source"), pk=pk)
    if request.method == "POST":
        source_id = card.source_id
        card.delete()
        return redirect("source_detail", pk=source_id)

    return render(
        request,
        "study/card_confirm_delete.html",
        {"card": card, "source": card.source},
    )
