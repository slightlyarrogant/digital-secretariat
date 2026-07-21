---
subject: "{{ company_name }} — prośba o wyciąg bankowy za {{ period }}"
required_params:
  - company_name
  - period
optional_params:
  - bank_hint
idem_key: "{{ company_id }}:{{ period }}"
category: reminder
cooldown_days: 7
description: >
  Prośba o miesięczny wyciąg bankowy — wysyłana automatycznie, gdy przy
  rozliczaniu miesiąca brakuje wyciągu. Idempotencja per firma+okres,
  dodatkowy cooldown 7 dni. bank_hint (opcjonalny) = lista znanych
  rachunków, o które prosimy.
---
Dzień dobry,

rozliczamy właśnie księgi {{ company_name }} za {{ period }} i do domknięcia
miesiąca brakuje nam jeszcze wyciągu bankowego
{%- if bank_hint %} dla rachunków:
{% for konto in bank_hint %}
- {{ konto }}
{%- endfor %}
{%- else %} z rachunku firmowego.
{%- endif %}

Prosimy o przesłanie wyciągu za {{ period }} w odpowiedzi na tego maila —
najwygodniej w formacie PDF pobranym z bankowości elektronicznej (zwykły
miesięczny wyciąg w zupełności wystarczy).

Wyciąg pozwala nam dopasować płatności do faktur i rozliczyć miesiąc bez
dopytywania o pojedyncze przelewy.

Dziękujemy i pozdrawiamy,
Zespół Digital Secretariat
