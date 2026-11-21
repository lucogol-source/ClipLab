# Regole per i prossimi sviluppi di ClipLab

Richiesta dell’utente del 20 novembre 2026. Applicare queste regole a ogni nuova versione dell’app.

- Mostrare sempre nel frontend la versione effettivamente in uso. Per i prossimi rilasci usare tre numeri, per esempio `V3.1.0` e `V3.1.1`, con una convenzione ispirata al [versionamento semantico](https://semver.org/lang/it/). Le versioni storiche a due numeri restano valide e non vanno rinominate retroattivamente.
- Incrementare il primo numero per cambiamenti incompatibili, per esempio che richiedono adattamenti dei progetti o delle integrazioni; il secondo per nuove funzioni e miglioramenti compatibili; il terzo per correzioni di bug e piccoli ritocchi senza nuove funzionalità. Quando aumenta un numero, azzerare quelli alla sua destra. Esempi: `3.0.0 → 3.1.0` per una funzione aggiuntiva, `3.1.0 → 3.1.1` per una correzione. Non assegnare un nuovo numero a ogni salvataggio: il numero identifica un rilascio verificato.
- Tenere allineati frontend, backend e pacchetti distribuiti, preferendo una sola fonte per il numero di versione. Non presentare una versione prevista come già installata. Prima di introdurre versioni nuove, verificare anche i controlli di versione nel launcher per evitare che confronti rigidi con `2.0` impediscano avvii o aggiornamenti.
- Mantenere una sola installazione corrente nella cartella `ClipLab`, preservandone percorso, progetti e configurazione. Indicare chiaramente la versione negli eventuali pacchetti di distribuzione.
- Prima di sostituire una versione funzionante con una nuova, conservarne codice e asset in una cartella locale di backup con nome esplicito, per esempio `../backup/ClipLab-V2.0`.
- Conservare soltanto il rilascio corrente e quello immediatamente precedente, comprese le revisioni minori e correttive. Esempio: con V3.1.1 corrente, mantenere V3.1.0 in backup e rimuovere il backup ancora precedente soltanto dopo aver verificato la nuova versione e la presenza del backup V3.1.0.
- La rotazione riguarda esclusivamente copie di rilascio dell’app identificate con certezza. Non eliminare né includere nella rotazione video, progetti, esportazioni, modelli, credenziali, token o cartelle create dall’utente di provenienza incerta.
- Non inventare un backup storico se non esiste una copia autentica della versione precedente. Non incrementare la versione soltanto per registrare queste istruzioni.
- Nella consegna di ogni nuovo rilascio indicare versione corrente e percorso del backup precedente. Evitare pacchetti duplicati della stessa versione; conservare un solo pacchetto corrente e, se utile, quello precedente nel backup.
- L’utente ha richiesto anche l’edizione Windows: per lo stesso rilascio sono ammessi due pacchetti distinti, con suffissi `-Mac` e `-Windows`. Mantenere il codice condiviso e la stessa versione. Non includere nei pacchetti `.data`, credenziali, video, ambienti Python o runtime installati su un altro computer. Includere sempre `README.txt`; distinguere test simulati da verifiche native Windows.
- Registrare per ogni rilascio data, modifiche e verifiche eseguite in un breve registro delle novità del progetto.

Alla registrazione di queste regole, backend e frontend indicano la versione 2.0. Nessuna nuova versione o rotazione è stata eseguita in questo passaggio.
