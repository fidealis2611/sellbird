# sellbird-warmup

Service d'échauffement et de délivrabilité auto-hébergé pour Sellbird.

Un réseau de boîtes (les tiennes) s'écrivent entre elles : envois progressifs, sortie du spam,
marquage important, réponses automatiques, taux de spam par boîte, pause automatique.

## Installer (Terminal du Mac, dossier du dépôt sellbird)

    source .venv/bin/activate && pip install -e extensions/sellbird_warmup

## Configurer : data/warmup/pool.yaml (les mots de passe restent dans .env)

    mailboxes:
      - address: contact@acme-mail.example
        display_name: Philippe
        bu: acme
        lang: fr
        smtp_host: ssl0.ovh.net
        imap_host: ssl0.ovh.net
        password_env: WARM_ACME_PASSWORD

## Utiliser

    sellbird warmpool status   # jour d'échauffement, taux de spam, réponses
    sellbird warmpool run      # un cycle immédiat
    sellbird warmpool pause|resume <adresse>

`sellbird run` exécute un cycle à chaque battement (étape `warmup.cycle`).

## Limites

- Il faut au moins 2 boîtes, idéalement 6 ou plus dont des Gmail et Outlook (rôle de boîtes témoins),
  sinon le signal de réputation vers ces fournisseurs reste faible.
- Le taux de spam mesuré est celui constaté dans les boîtes du réseau, pas chez tous les fournisseurs.
