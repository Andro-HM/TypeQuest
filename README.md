# TypeQuest: Week 1 Frontend Demo

A small Classic typing game with three freely selectable, fixed passages. Type in a normal textarea, see positional character highlights and live metrics, then view your result and retry or choose another level.

## Run

Open `index.html` directly in current Chrome or Edge. No server, installation, or internet connection is needed. Keep the three source files together so their relative paths work.

## Files

- `index.html`: the Home, Play, level-selection, typing, and results sections, plus their buttons and metric displays.
- `style.css`: navy/teal styling, character colors, and responsive layouts.
- `script.js`: three original passages, attempt state, event handlers, timing, metric calculations, and section visibility.

## Follow the JavaScript

1. Home and Play call `showHome()` and `showPlay()`. Start playing also opens Play; Play Classic then calls `showLevelSelection()` to open the three level choices. `showScreen()` displays the selected section and marks the active navigation tab.
2. A level button calls `startLevel()`. It loads the passage, clears the previous attempt, renders untouched characters, and focuses the textarea. Retry calls the same function for the current level.
3. Native typing and editing trigger `handleTyping()`. The first non-empty input starts the timestamp timer and a 100 ms display refresh.
4. `updateHighlighting()` compares each entered character with the same target position. `countCorrectCharacters()` supplies the matching count to `updateMetrics()`.
5. `updateMetrics()` calculates raw WPM, accuracy, and net WPM from the current text and elapsed time. Values are rounded only for display; an empty denominator gives zero.
6. Reaching the target length calls `finishLevel()`, which stops timing, disables input, and displays the final metrics. Incorrect characters do not prevent completion.
7. `restrictTyping()` blocks paste, dropped text, and Enter/line-break input. The textarea's `maxlength` and an input cleanup loop also enforce the length and single-line limits.
8. Pause calls `pauseLevel()`, which saves the elapsed active time and disables typing. Play calls `playLevel()`, which adjusts the start timestamp so the saved time continues without including the break.

Backspace, selection, insertion, replacement, and cursor movement use normal browser textarea behavior. Deleting all text after the timer starts does not restart the timer. Each new attempt resets it.

Leaving a typing attempt through Home or Play pauses its timer. Selecting a level starts a fresh attempt. Progress, Profiles, Settings, Time Attack, and Survival are disabled placeholders.

## Intentionally absent

There are no profiles, storage, saved scores, database, backend requests, unlocking, stars, other game modes, settings, or audio. Results exist only for the current attempt. The Flask applications on `main` and `week1-demo` are separate from this prototype.
