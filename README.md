# GIovani-Testing
Coba coba aja

## Garuda Chess

A simple two-player chess game with a Timnas Indonesia theme. Single file, no dependencies, no build step.

### Run
Open `index.html` in any modern browser. Red (Merah) moves first; players take turns on the same screen. There is no computer opponent.

### Features
- Legal-move checking, check, checkmate and stalemate
- Castling and en passant
- Pawn promotion (always to queen)
- Highlighted selection, legal moves, captures and king in check
- "New game" button

### Theme
Each piece is a cartoon face on a Garuda jersey (red or white) with a player's surname and a piece symbol. The faces are generic illustrations, not photographs of the players.

| Piece | Player |
|---|---|
| King | Idzes (captain) |
| Queen | Verdonk |
| Rook | Baggott |
| Bishop | Walsh |
| Knight | Ridho |
| Pawn | "Garuda" |

Names are taken from the June 2026 squad. To change them, edit the `ROSTER` object at the top of the script in `index.html`.

### Known limitations
- Promotion is always to a queen
- No draw detection for repetition, fifty-move rule or insufficient material
- No undo, clock or move history
