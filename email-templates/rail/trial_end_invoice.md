---
subject: "{{ company_name }} — koniec okresu próbnego, faktura za {{ period }}"
required_params:
  - company_name
  - period
  - amount_summary
idem_key: "{{ company_id }}:{{ period }}"
category: billing
description: >
  Zawiadomienie o końcu okresu próbnego + faktura za usługi księgowe
  (fakturę dołącza wywołujący jako załącznik). amount_summary = wolny
  tekst z podsumowaniem kwot, np. "Obsługa księgowa za czerwiec 2026:
  499,00 zł netto (613,77 zł brutto), termin płatności 14 dni".
  period w mianowniku, np. "czerwiec 2026". Idempotencja per firma+okres.
---
Dzień dobry,

okres próbny obsługi księgowej {{ company_name }} w Digital Secretariat właśnie dobiegł
końca ({{ period }} był ostatnim miesiącem próbnym). Dziękujemy za zaufanie —
cieszymy się, że możemy dalej prowadzić Państwa księgi.

Od bieżącego okresu obsługa rozliczana jest już standardowo. W załączniku
przesyłamy fakturę:

{{ amount_summary }}

Zakres usług pozostaje bez zmian — nadal wystarczy przesyłać nam dokumenty
mailem, a rozliczenia, deklaracje i przypomnienia o terminach są po naszej
stronie.

Jeśli mają Państwo pytania do faktury albo zakresu obsługi, wystarczy
odpowiedzieć na tego maila.

Dziękujemy i pozdrawiamy,
Zespół Digital Secretariat
