from django import forms


class SourceForm(forms.Form):
    title = forms.CharField(max_length=120, label="Название")
    text = forms.CharField(
        widget=forms.Textarea,
        min_length=50,
        label="Конспект",
    )

    def clean_text(self):
        return self.cleaned_data["text"].replace("\r\n", "\n")
