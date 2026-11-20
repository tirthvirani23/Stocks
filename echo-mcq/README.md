# Echo MCQ Practice

An offline study app for all 500 MCQs from *Echocardiography Board Review: 500 Multiple Choice Questions with Discussion* (2nd ed., Pai & Varadarajan). The questions are kept in the book's order, and the figures and the book's explanations are included.

## Two ways to use it

1. **`echo-mcq-offline.html` (simplest).** This single file of about 10 MB holds every question and figure. Copy it to any device and open it in a browser. It needs no internet connection.
2. **Hosted PWA (`index.html` with `data.js`, `img/` and `sw.js`).** Serve this folder over HTTPS, for example with GitHub Pages or Netlify. On the first visit, a service worker downloads all the questions and figures. After that the app works offline and can be installed with "Add to Home Screen".

## Features
- Tap an option to mark your answer. The app then says True or False against the book's key and shows the book's explanation underneath.
- Flag questions to revisit later. A filter can show only flagged, incorrect or unanswered questions.
- The header shows the percentage completed and the percentage correct. The navigator (☰) shows progress for each chapter.
- Progress is saved in the browser on each device. You can use Export/Import to move it between devices.
- Includes dark mode, tap-to-zoom figures and keyboard shortcuts (A–F to answer, ←/→ to move, F to flag).

`build_single.py` rebuilds `echo-mcq-offline.html` from `index.html`, `data.js` and `img/`.
