# Deadlock Item Randomizer – offentlig hosting

Denne pakke gør appen klar til hosting, så andre kan åbne den via et offentligt HTTPS-link uden at være på samme Wi‑Fi.

## Udgiv via Render

1. Opret/log ind på GitHub, og opret et nyt repository.
2. Upload `app.py`, `requirements.txt` og `render.yaml` til repository'et.
3. Gå til https://render.com/ og opret en ny **Blueprint** fra repository'et.
4. Render læser `render.yaml`, installerer afhængighederne og bygger appen.
5. Når deployment er færdigt, giver Render dig en offentlig `https://...onrender.com`-adresse. Del den med din medspiller.

## Vigtigt om lobbyen

- Brug én fælles offentlig URL for alle spillere.
- Denne opsætning bruger én Gunicorn-worker, fordi den nuværende lobbytilstand ligger i appens hukommelse. Flere workers kan få forskellige spillere til at se forskellig tilstand.
- Hvis serveren genstarter eller går i dvale, kan lobbyen nulstilles. Start en ny lobby, hvis det sker.
- Linket er offentligt: alle med adressen kan forsøge at åbne appen. Del ikke følsomme oplysninger i spillernavne.
- Sæt ikke debug-tilstand til i en offentlig deployment.

## Lokal kørsel

`python app.py` virker fortsat lokalt. Til lokal brug skal alle på samme Wi‑Fi stadig bruge værtens lokale IP; til fjernspillere bruges den offentlige Render-adresse.
