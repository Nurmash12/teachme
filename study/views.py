from django.db import DatabaseError, transaction
from django.shortcuts import get_object_or_404, redirect, render

from .forms import SourceForm
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
    return render(
        request,
        "study/source_detail.html",
        {"source": source},
    )
