from django import forms

from .models import Flashcard


class SourceForm(forms.Form):
    title = forms.CharField(max_length=120, label="Название")
    text = forms.CharField(
        widget=forms.Textarea,
        min_length=50,
        label="Конспект",
    )

    def clean_text(self):
        return self.cleaned_data["text"].replace("\r\n", "\n")


class FlashcardForm(forms.ModelForm):
    class Meta:
        model = Flashcard
        fields = ["question", "answer", "source_quote"]
        labels = {
            "question": "Вопрос",
            "answer": "Ответ",
            "source_quote": "Цитата из конспекта",
        }
        widgets = {
            "answer": forms.Textarea,
            "source_quote": forms.Textarea,
        }

    def __init__(self, *args, source_text=None, **kwargs):
        super().__init__(*args, **kwargs)
        if source_text is None and self.instance.pk:
            source_text = self.instance.source.text
        self.source_text = source_text

    def clean_source_quote(self):
        quote = self.cleaned_data["source_quote"]
        if self.source_text is None or quote not in self.source_text:
            raise forms.ValidationError(
                "Цитата должна присутствовать в исходном конспекте."
            )
        return quote
