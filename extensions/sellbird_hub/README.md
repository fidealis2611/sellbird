# sellbird-hub

Un espace Sellbird par business unit, plus : langue par pays, messages par taille, rapport Excel quotidien,
envoi automatique au CRM avec anti-doublons sur toute la periode.

## Installer (Terminal du Mac, dossier sellbird)

    source .venv/bin/activate && pip install -e extensions/sellbird_hub

## Reglages communs : workspaces/hub.yaml

    report:
      recipients: [reports@example.com]
      from: sellbird@example.com
      hour: 18
    crm:
      url: https://crm.example.com/add_lead
      token_env: CRM_TOKEN
      default_agent_id: 140
      agent_id_by_bu: {acme: 140}

Mettre RESEND_API_KEY et CRM_TOKEN dans le .env du dossier sellbird.

## Commandes

    sellbird hub add <id> ...        creer une BU
    sellbird hub report --send       rapport Excel du jour, envoye par email
    sellbird hub crm-push --dry-run  voir ce qui partirait au CRM
    sellbird hub daily               rapport + email + CRM (a lancer chaque soir)
    sellbird hub launchd             fichier de planification macOS
