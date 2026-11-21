#!/bin/zsh
set -eu
cd -- "$(dirname -- "$0")"
if [[ ! -x .venv/bin/python ]]; then
  print 'Esegui prima Avvia ClipLab.command per installare i componenti gratuiti.'
  read '?Premi Invio per chiudere.'
  exit 1
fi
print 'Preparazione dei modelli locali gratuiti per sottotitoli e tracking…'
exec .venv/bin/python prepare_models.py --small
