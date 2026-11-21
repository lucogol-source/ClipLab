# ClipLab 2.0 — confronto e scelte

Ricerca sulle funzionalità dichiarate nei siti e nelle guide ufficiali, 19 novembre 2026. Non è una prova comparativa dei servizi a pagamento e non garantisce risultati di viralità.

| Riferimento | Punto di forza utile | Applicazione in ClipLab |
| --- | --- | --- |
| [OpusClip](https://www.opus.pro/) | Reframing automatico con controllo manuale e flusso clipping–editing–pubblicazione. | Tracking volti locale, zoom e pan manuale, punti di movimento modificabili. Non replica il loro modello proprietario di comprensione video. |
| [Vizard](https://vizard.ai/) | Editor con trascrizione, cambio formato e timeline. | Editor con anteprima canvas, tempi dei tagli, posizionamento dell’immagine, traccia sottotitoli modificabile e salvataggio delle modifiche. |
| [quso.ai](https://quso.ai/products/ai-social-media-manager) | Programmazione e pubblicazione su più social. | Coda locale persistente per YouTube e TikTok, prima data e intervallo tra clip, pausa, annullamento e stato di ogni invio. |
| [2short.ai](https://2short.ai/) | Facial tracking, sottotitoli animati ed esportazioni adattabili. | Rilevamento YuNet gratuito sul Mac, scelta volto predominante/sinistro/destro, evidenziazione della singola parola corrente. |
| [NoonFrame](https://noonframe.com/en/) | App desktop e passaggio semplice da registrazione lunga a clip verticali con editor. | Elaborazione locale, nessuna quota di minuti acquistata, layout di esportazione e interfaccia focalizzata sulla revisione delle clip. |
| [WayinVideo](https://help.wayin.ai/en/articles/16210969-video-editor-overview) | Workspace con anteprima, timeline, reframing e sottotitoli. | Strumenti dell’editor divisi in Inquadratura, Sottotitoli ed Esporta/pubblica. |

Le funzionalità e i limiti gratuiti di questi servizi dipendono dai rispettivi piani. ClipLab non chiama le loro API e non usa i loro abbonamenti: prende come riferimento le idee di prodotto e utilizza componenti locali gratuiti. Non sono stati copiati codice, modelli proprietari o identità visive dei servizi.

## Sottotitoli

- Whisper Small come scelta più accurata per i nuovi progetti; Base e Tiny rimangono disponibili per la velocità.
- Ritrascrizione della singola clip, senza rielaborare l’intero video lungo, con glossario di nomi e termini.
- Modifica di testo e tempi di ogni blocco; quando il testo viene riscritto, i tempi delle parole sono stimati entro il blocco e devono essere controllati.
- Blocchi automatici brevi, font leggibile, contorno, margini e colore regolabili. L’evidenziazione riguarda la parola corrente.
- Esportazione MP4 con testo impresso e SRT separato.

Il modello più grande non elimina gli errori. Nomi di persone, località e numeri richiedono revisione. I modelli vengono scaricati una volta; trascrizione e rendering avvengono sul Mac.

## Inquadratura ed editor

- Formati 9:16, 1:1 e 16:9, uscite 1080p o 720p.
- Ritaglio a schermo pieno, immagine intera con bande o sfondo sfocato, podcast con due riquadri sovrapposti.
- Pan orizzontale/verticale, zoom da 1× a 3×, trascinamento nell’anteprima e punti di movimento interpolati.
- Tracking volti locale YuNet: scelta del volto predominante oppure del volto a sinistra/destra. È un inseguimento visivo: non è diarizzazione audio né identificazione infallibile di chi sta parlando. Per due ospiti resta disponibile il layout doppio e la regolazione manuale.
- Nessun watermark aggiunto da ClipLab. I loghi già presenti nel video sorgente rimangono nell’immagine.

Il modello YuNet proviene da [OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet), con la relativa licenza del progetto/modello; l’app usa OpenCV e FFmpeg per il rendering.

## Pubblicazioni

Le clip vengono prima esportate e poi selezionate per la coda. La conferma comprende canali, visibilità, titoli e orari. Ogni lavoro conserva l’ID dell’esportazione e la revisione approvata: una modifica successiva blocca la vecchia programmazione e richiede una nuova esportazione/approvazione. Gli invii incerti non vengono ripetuti automaticamente, per evitare duplicati.

La coda è salvata in SQLite e continua dopo il riavvio dell’app. Il Mac deve restare acceso, con ClipLab e la connessione in funzione. Dopo una sospensione del Mac non vengono inviati tutti i lavori arretrati insieme: viene mantenuto l’intervallo tra gli invii dello stesso gruppo. Non è un servizio cloud sempre acceso.

### Limite concreto di TikTok

Il collegamento implementa Login Kit Desktop con PKCE e Content Posting API ufficiali. Servono le credenziali di un’app TikTok e i permessi appropriati. Una connessione Google non autorizza TikTok.

Gli upload da client non sottoposti ad audit sono limitati a visualizzazione privata e account privati. Per Direct Post pubblico occorre l’approvazione di TikTok, che esclude alcuni strumenti limitati all’uso personale e app che copiano arbitrariamente contenuti da altre piattaforme. Non è garantito che un’app personale venga approvata. Non sono previsti aggiramenti tramite browser, cookie o servizi esterni.

Le opzioni di visibilità e durata sono lette dall’account prima della pubblicazione. La visibilità TikTok non è preselezionata; l’utente conferma contenuto e uso della musica per le clip scelte. L’esito “pubblicato” viene mostrato soltanto dopo conferma della piattaforma, distinto dall’avvenuto trasferimento del file.

Fonti: [linee guida TikTok](https://developers.tiktok.com/doc/content-sharing-guidelines), [Login Kit Desktop](https://developers.tiktok.com/doc/login-kit-desktop/), [Direct Post](https://developers.tiktok.com/doc/content-posting-api-reference-direct-post), [informazioni del creator](https://developers.tiktok.com/doc/content-posting-api-reference-query-creator-info), [trasferimento file](https://developers.tiktok.com/doc/content-posting-api-media-transfer-guide).
