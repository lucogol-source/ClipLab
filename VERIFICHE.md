# Verifiche della versione 2.0

- 20 test Python superati: tagli, sottotitoli, geometria, movimento, autorizzazioni, pubblicazione simulata e coda persistente.
- Test JavaScript superato per perdita/ripristino della connessione; nessuna ripetizione automatica delle richieste che modificano dati. Controllata la sintassi dei tre script.
- Prova effettiva con video di test di 4 secondi: tracking volti e rendering dei cinque casi ritaglio, bande, sfondo sfocato, doppio riquadro e movimento adattivo. Verificati 1080×1920, durata, audio AAC, SRT e assenza di watermark aggiunti.
- Prova nell’interfaccia: modifica e salvataggio di un sottotitolo, cambio layout, esportazione aggiornata e apertura della programmazione con account non collegati.
- Prova sul video YouTube fornito: ritrascrizione della prima clip con Whisper Small locale, revisione manuale dei sottotitoli e nuovo taglio da 11:21.05 a 12:06.40. MP4 H.264/AAC di 45,37 secondi a 1080×1920, con immagine intera e sfondo sfocato. Esempio disponibile accanto alla cartella dell’app come `ClipLab-2-esempio.mp4` e SRT.
- Verificato SHA-256 del modello Small scaricato, prima del suo utilizzo.

Le prove non hanno pubblicato video su account reali. YouTube e TikTok devono essere collegati dal proprietario. TikTok può consentire soltanto invii privati o rifiutare l’accesso richiesto, secondo la propria approvazione. Il tracking segue i volti e non riconosce il parlante dall’audio. La selezione delle clip usa criteri locali sul parlato e non prevede la viralità.

Il pacchetto ZIP esclude progetti, modelli, ambienti Python, credenziali e token. Sul Mac attuale rimangono installati e utilizzabili nella cartella già esistente.
