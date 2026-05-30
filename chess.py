"""
chess_game.py  –  Jeu d'échecs  (Humain vs IA)
Architecture : Moteur | Rendu | JoueurIA | EtatPartie | Application
Coups spéciaux : Roque petit/grand, Prise en passant, Promotion interactive
"""

from __future__ import annotations

import pytest
import copy
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import pygame

# ═══════════════════════════════════════════════════════════════════
#  CONSTANTES
# ═══════════════════════════════════════════════════════════════════

class Color(str, Enum):
    WHITE = "blanc"
    BLACK = "noir"

    @property
    def opponent(self) -> "Color":
        return Color.BLACK if self == Color.WHITE else Color.WHITE


class PieceType(str, Enum):
    PAWN   = "pion"
    ROOK   = "tour"
    KNIGHT = "cavalier"
    BISHOP = "fou"
    QUEEN  = "reine"
    KING   = "roi"


class GameMode(Enum):
    VS_AI       = "Humain vs IA"
    VS_HUMAN    = "2 Joueurs"


PIECE_VALUES: dict[PieceType, int] = {
    PieceType.PAWN:   100,
    PieceType.KNIGHT: 320,
    PieceType.BISHOP: 330,
    PieceType.ROOK:   500,
    PieceType.QUEEN:  900,
    PieceType.KING:   20_000,
}

PIECE_SYMBOLS: dict[str, str] = {
    "blanc_roi": "♔", "blanc_reine": "♕", "blanc_tour": "♖",
    "blanc_fou": "♗", "blanc_cavalier": "♘", "blanc_pion": "♙",
    "noir_roi":  "♚", "noir_reine":  "♛", "noir_tour":  "♜",
    "noir_fou":  "♝", "noir_cavalier": "♞", "noir_pion":  "♟",
}

# Choix de promotion disponibles pour le joueur
PROMOTION_TYPES = [PieceType.QUEEN, PieceType.ROOK, PieceType.KNIGHT, PieceType.BISHOP]

# Tables de positionnement (perspective Blancs ; inversées pour les Noirs)
_PST: dict[PieceType, list[list[int]]] = {
    PieceType.PAWN: [
        [ 0,  0,  0,  0,  0,  0,  0,  0],
        [50, 50, 50, 50, 50, 50, 50, 50],
        [10, 10, 20, 30, 30, 20, 10, 10],
        [ 5,  5, 10, 25, 25, 10,  5,  5],
        [ 0,  0,  0, 20, 20,  0,  0,  0],
        [ 5, -5,-10,  0,  0,-10, -5,  5],
        [ 5, 10, 10,-20,-20, 10, 10,  5],
        [ 0,  0,  0,  0,  0,  0,  0,  0],
    ],
    PieceType.KNIGHT: [
        [-50,-40,-30,-30,-30,-30,-40,-50],
        [-40,-20,  0,  0,  0,  0,-20,-40],
        [-30,  0, 10, 15, 15, 10,  0,-30],
        [-30,  5, 15, 20, 20, 15,  5,-30],
        [-30,  0, 15, 20, 20, 15,  0,-30],
        [-30,  5, 10, 15, 15, 10,  5,-30],
        [-40,-20,  0,  5,  5,  0,-20,-40],
        [-50,-40,-30,-30,-30,-30,-40,-50],
    ],
    PieceType.BISHOP: [
        [-20,-10,-10,-10,-10,-10,-10,-20],
        [-10,  0,  0,  0,  0,  0,  0,-10],
        [-10,  0,  5, 10, 10,  5,  0,-10],
        [-10,  5,  5, 10, 10,  5,  5,-10],
        [-10,  0, 10, 10, 10, 10,  0,-10],
        [-10, 10, 10, 10, 10, 10, 10,-10],
        [-10,  5,  0,  0,  0,  0,  5,-10],
        [-20,-10,-10,-10,-10,-10,-10,-20],
    ],
    PieceType.ROOK: [
        [ 0,  0,  0,  0,  0,  0,  0,  0],
        [ 5, 10, 10, 10, 10, 10, 10,  5],
        [-5,  0,  0,  0,  0,  0,  0, -5],
        [-5,  0,  0,  0,  0,  0,  0, -5],
        [-5,  0,  0,  0,  0,  0,  0, -5],
        [-5,  0,  0,  0,  0,  0,  0, -5],
        [-5,  0,  0,  0,  0,  0,  0, -5],
        [ 0,  0,  0,  5,  5,  0,  0,  0],
    ],
    PieceType.QUEEN: [
        [-20,-10,-10, -5, -5,-10,-10,-20],
        [-10,  0,  0,  0,  0,  0,  0,-10],
        [-10,  0,  5,  5,  5,  5,  0,-10],
        [ -5,  0,  5,  5,  5,  5,  0, -5],
        [  0,  0,  5,  5,  5,  5,  0, -5],
        [-10,  5,  5,  5,  5,  5,  0,-10],
        [-10,  0,  5,  0,  0,  0,  0,-10],
        [-20,-10,-10, -5, -5,-10,-10,-20],
    ],
    PieceType.KING: [
        [-30,-40,-40,-50,-50,-40,-40,-30],
        [-30,-40,-40,-50,-50,-40,-40,-30],
        [-30,-40,-40,-50,-50,-40,-40,-30],
        [-30,-40,-40,-50,-50,-40,-40,-30],
        [-20,-30,-30,-40,-40,-30,-30,-20],
        [-10,-20,-20,-20,-20,-20,-20,-10],
        [ 20, 20,  0,  0,  0,  0, 20, 20],
        [ 20, 30, 10,  0,  0, 10, 30, 20],
    ],
}

# Géométrie de l'interface
BOARD_SIZE = 560
SQ         = BOARD_SIZE // 8
MARGIN     = 36
PANEL_W    = 260
WIN_W      = MARGIN + BOARD_SIZE + MARGIN + PANEL_W
WIN_H      = MARGIN + BOARD_SIZE + MARGIN
BOARD_X    = MARGIN
BOARD_Y    = MARGIN
AI_DEPTH   = 3
PIECE_SCALE = 0.78   # fraction de SQ (0.0–1.0) ; réduire pour diminuer la taille des pièces
PIECE_SZ    = int(SQ * PIECE_SCALE)
PIECE_OFFSET = (SQ - PIECE_SZ) // 2   # décalage pour centrer la pièce dans la case

IMAGES_DIR       = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
PIECE_EXTENSIONS = (".png", ".jpg", ".jpeg")

C = {
    "bg":         (15,  12,  10),
    "sq_dark":    (58,  37,  20),
    "sq_light":   (205, 170, 125),
    "gold":       (212, 175,  55),
    "gold2":      (255, 215, 100),
    "coord":      (160, 120,  70),
    "panel_bg":   (22,  18,  14),
    "panel_line": (50,  38,  22),
    "text":       (230, 220, 200),
    "dim":        (120, 100,  70),
    "grey":       (160, 160, 160),
    "green":      (100, 180, 100),
    "red":        (200,  60,  40),
    "blue":       (100, 150, 255),
    "promo_bg":   (30,  24,  18),
    "promo_hover":(70,  55,  30),
}

# ═══════════════════════════════════════════════════════════════════
#  ALIAS DE TYPES ET UTILITAIRES
# ═══════════════════════════════════════════════════════════════════

Board  = list[list[str]]
Square = tuple[int, int]
Move   = tuple[Square, Square]


def piece_color(piece: str) -> Color:
    return Color.WHITE if piece.startswith("blanc") else Color.BLACK

def piece_type(piece: str) -> PieceType:
    return PieceType(piece.split("_", 1)[1])

def on_board(r: int, c: int) -> bool:
    return 0 <= r < 8 and 0 <= c < 8

def sq_to_alg(r: int, c: int) -> str:
    return "abcdefgh"[c] + str(8 - r)

def is_promotion_move(board: Board, src: Square, dst: Square) -> bool:
    """Retourne True si le coup de src vers dst provoque une promotion."""
    piece = board[src[0]][src[1]]
    if not piece:
        return False
    pt    = piece_type(piece)
    color = piece_color(piece)
    return (pt == PieceType.PAWN
            and ((color == Color.WHITE and dst[0] == 0)
                 or (color == Color.BLACK and dst[0] == 7)))

def is_castling_move(board: Board, src: Square, dst: Square) -> Optional[str]:
    """Retourne 'kingside', 'queenside' ou None selon le type de roque."""
    piece = board[src[0]][src[1]]
    if not piece or piece_type(piece) != PieceType.KING:
        return None
    _, sc = src
    _, dc = dst
    if dc == sc + 2:
        return "kingside"
    if dc == sc - 2:
        return "queenside"
    return None

def is_en_passant_move(board: Board, src: Square, dst: Square,
                       ep: Optional[Square]) -> bool:
    piece = board[src[0]][src[1]]
    if not piece or piece_type(piece) != PieceType.PAWN:
        return False
    return ep is not None and dst == ep


# ═══════════════════════════════════════════════════════════════════
#  MOTEUR D'ÉCHECS  (pur, sans état)
# ═══════════════════════════════════════════════════════════════════

class Engine:

    # ── Générateurs de coups bruts ─────────────────────────────────

    @staticmethod
    def _pawn_moves(board: Board, r: int, c: int,
                    color: Color, ep: Optional[Square]) -> list[Square]:
        moves: list[Square] = []
        d     = -1 if color == Color.WHITE else 1
        start =  6 if color == Color.WHITE else 1

        if on_board(r + d, c) and not board[r + d][c]:
            moves.append((r + d, c))
            if r == start and not board[r + 2 * d][c]:
                moves.append((r + 2 * d, c))

        for dc in (-1, 1):
            nr, nc = r + d, c + dc
            if on_board(nr, nc):
                if board[nr][nc] and piece_color(board[nr][nc]) != color:
                    moves.append((nr, nc))
                if ep == (nr, nc):
                    moves.append((nr, nc))
        return moves

    @staticmethod
    def _knight_moves(board: Board, r: int, c: int, color: Color) -> list[Square]:
        return [
            (r + dr, c + dc)
            for dr, dc in ((2,1),(1,2),(-1,2),(-2,1),(-2,-1),(-1,-2),(1,-2),(2,-1))
            if on_board(r + dr, c + dc)
            and (not board[r + dr][c + dc]
                 or piece_color(board[r + dr][c + dc]) != color)
        ]

    @staticmethod
    def _sliding_moves(board: Board, r: int, c: int,
                       color: Color, directions: tuple) -> list[Square]:
        moves: list[Square] = []
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            while on_board(nr, nc):
                if not board[nr][nc]:
                    moves.append((nr, nc))
                else:
                    if piece_color(board[nr][nc]) != color:
                        moves.append((nr, nc))
                    break
                nr += dr
                nc += dc
        return moves

    @staticmethod
    def _king_moves(board: Board, r: int, c: int,
                    color: Color, castling: dict) -> list[Square]:
        moves: list[Square] = [
            (r + dr, c + dc)
            for dr in (-1, 0, 1) for dc in (-1, 0, 1)
            if (dr, dc) != (0, 0)
            and on_board(r + dr, c + dc)
            and (not board[r + dr][c + dc]
                 or piece_color(board[r + dr][c + dc]) != color)
        ]
        back = 7 if color == Color.WHITE else 0
        cv   = color.value

        if r == back and c == 4:
            # Petit roque : le roi passe e→f→g, tour en h
            if (castling[cv]["kingside"]
                    and not board[back][5] and not board[back][6]
                    and not Engine.is_check(board, color)):
                tmp = copy.deepcopy(board)
                tmp[back][5] = cv + "_roi"
                tmp[back][4] = ""
                if not Engine.is_check(tmp, color):
                    moves.append((back, 6))

            # Grand roque : le roi passe e→d→c, tour en a
            if (castling[cv]["queenside"]
                    and not board[back][3] and not board[back][2] and not board[back][1]
                    and not Engine.is_check(board, color)):
                tmp = copy.deepcopy(board)
                tmp[back][3] = cv + "_roi"
                tmp[back][4] = ""
                if not Engine.is_check(tmp, color):
                    moves.append((back, 2))

        return moves

    # ── Interface publique ──────────────────────────────────────────

    @staticmethod
    def pseudo_moves(board: Board, r: int, c: int,
                     ep: Optional[Square] = None,
                     castling: Optional[dict] = None) -> list[Square]:
        piece = board[r][c]
        if not piece:
            return []
        color = piece_color(piece)
        pt    = piece_type(piece)
        if castling is None:
            castling = Engine.default_castling()

        match pt:
            case PieceType.PAWN:
                return Engine._pawn_moves(board, r, c, color, ep)
            case PieceType.KNIGHT:
                return Engine._knight_moves(board, r, c, color)
            case PieceType.BISHOP:
                return Engine._sliding_moves(board, r, c, color,
                                             ((1,1),(1,-1),(-1,1),(-1,-1)))
            case PieceType.ROOK:
                return Engine._sliding_moves(board, r, c, color,
                                             ((1,0),(-1,0),(0,1),(0,-1)))
            case PieceType.QUEEN:
                return Engine._sliding_moves(board, r, c, color,
                                             ((1,0),(-1,0),(0,1),(0,-1),
                                              (1,1),(1,-1),(-1,1),(-1,-1)))
            case PieceType.KING:
                return Engine._king_moves(board, r, c, color, castling)
        return []

    @staticmethod
    def legal_moves(board: Board, r: int, c: int,
                    ep: Optional[Square], castling: dict) -> list[Square]:
        piece = board[r][c]
        if not piece:
            return []
        color  = piece_color(piece)
        result: list[Square] = []
        for dst in Engine.pseudo_moves(board, r, c, ep, castling):
            tmp = copy.deepcopy(board)
            Engine.apply_move(tmp, (r, c), dst, ep,
                              {"blanc": {"kingside": True, "queenside": True},
                               "noir":  {"kingside": True, "queenside": True}},
                              promotion=PieceType.QUEEN)   # reine temporaire pour vérifier la légalité
            if not Engine.is_check(tmp, color):
                result.append(dst)
        return result

    @staticmethod
    def all_legal_moves(board: Board, color: Color,
                        ep: Optional[Square], castling: dict) -> list[Move]:
        moves: list[Move] = []
        for r in range(8):
            for c in range(8):
                p = board[r][c]
                if p and piece_color(p) == color:
                    for dst in Engine.legal_moves(board, r, c, ep, castling):
                        moves.append(((r, c), dst))
        return moves

    @staticmethod
    def find_king(board: Board, color: Color) -> Optional[Square]:
        target = color.value + "_roi"
        for r in range(8):
            for c in range(8):
                if board[r][c] == target:
                    return (r, c)
        return None

    @staticmethod
    def is_check(board: Board, color: Color) -> bool:
        king_pos = Engine.find_king(board, color)
        if not king_pos:
            return False
        kr, kc = king_pos
        enemy  = color.opponent
        for r in range(8):
            for c in range(8):
                p = board[r][c]
                if not p or piece_color(p) != enemy:
                    continue
                pt = piece_type(p)
                match pt:
                    case PieceType.PAWN:
                        raw = Engine._pawn_moves(board, r, c, enemy, None)
                    case PieceType.KNIGHT:
                        raw = Engine._knight_moves(board, r, c, enemy)
                    case PieceType.BISHOP:
                        raw = Engine._sliding_moves(board, r, c, enemy,
                                                    ((1,1),(1,-1),(-1,1),(-1,-1)))
                    case PieceType.ROOK:
                        raw = Engine._sliding_moves(board, r, c, enemy,
                                                    ((1,0),(-1,0),(0,1),(0,-1)))
                    case PieceType.QUEEN:
                        raw = Engine._sliding_moves(board, r, c, enemy,
                                                    ((1,0),(-1,0),(0,1),(0,-1),
                                                     (1,1),(1,-1),(-1,1),(-1,-1)))
                    case PieceType.KING:
                        raw = [(r+dr, c+dc)
                               for dr in (-1,0,1) for dc in (-1,0,1)
                               if (dr,dc) != (0,0) and on_board(r+dr, c+dc)]
                    case _:
                        raw = []
                if (kr, kc) in raw:
                    return True
        return False

    @staticmethod
    def apply_move(board: Board, src: Square, dst: Square,
                   ep: Optional[Square], castling: dict,
                   promotion: PieceType = PieceType.QUEEN) -> Optional[Square]:
        """
        Applique le coup sur le plateau (en place). Gère :
          • Coups normaux
          • Prise en passant
          • Petit roque / grand roque
          • Promotion du pion (vers la pièce choisie)
        Retourne la nouvelle cible de prise en passant, ou None.
        """
        sr, sc = src
        dr, dc = dst
        piece  = board[sr][sc]
        color  = piece_color(piece)
        cv     = color.value
        pt     = piece_type(piece)
        new_ep: Optional[Square] = None

        # ── Prise en passant ─────────────────────────────────────────
        if pt == PieceType.PAWN and ep == (dr, dc):
            board[sr][dc] = ""      # supprime le pion capturé sur la même rangée

        # ── Roque : déplacement de la tour ───────────────────────────
        if pt == PieceType.KING:
            if dc == sc + 2:        # petit roque  (O-O)
                board[dr][5] = cv + "_tour"
                board[dr][7] = ""
            elif dc == sc - 2:      # grand roque (O-O-O)
                board[dr][3] = cv + "_tour"
                board[dr][0] = ""

        # ── Déplacement de la pièce ──────────────────────────────────
        board[dr][dc] = piece
        board[sr][sc] = ""

        # ── Promotion du pion ─────────────────────────────────────────
        if pt == PieceType.PAWN:
            if (color == Color.WHITE and dr == 0) or (color == Color.BLACK and dr == 7):
                board[dr][dc] = cv + "_" + promotion.value

        # ── Cible en passant pour le prochain coup ───────────────────
        if pt == PieceType.PAWN and abs(dr - sr) == 2:
            new_ep = ((sr + dr) // 2, dc)

        # ── Mise à jour des droits de roque ────────────────────────
        if piece == "blanc_roi":
            castling["blanc"]["kingside"] = castling["blanc"]["queenside"] = False
        if piece == "noir_roi":
            castling["noir"]["kingside"]  = castling["noir"]["queenside"]  = False
        if piece == "blanc_tour":
            if sc == 7: castling["blanc"]["kingside"]  = False
            if sc == 0: castling["blanc"]["queenside"] = False
        if piece == "noir_tour":
            if sc == 7: castling["noir"]["kingside"]  = False
            if sc == 0: castling["noir"]["queenside"] = False

        return new_ep

    @staticmethod
    def has_legal_move(board: Board, color: Color,
                       ep: Optional[Square], castling: dict) -> bool:
        for r in range(8):
            for c in range(8):
                p = board[r][c]
                if p and piece_color(p) == color:
                    if Engine.legal_moves(board, r, c, ep, castling):
                        return True
        return False

    @staticmethod
    def default_castling() -> dict:
        return {
            "blanc": {"kingside": True, "queenside": True},
            "noir":  {"kingside": True, "queenside": True},
        }

    @staticmethod
    def initial_board() -> Board:
        return [
            ["noir_tour","noir_cavalier","noir_fou","noir_reine",
             "noir_roi","noir_fou","noir_cavalier","noir_tour"],
            ["noir_pion"] * 8,
            [""] * 8, [""] * 8, [""] * 8, [""] * 8,
            ["blanc_pion"] * 8,
            ["blanc_tour","blanc_cavalier","blanc_fou","blanc_reine",
             "blanc_roi","blanc_fou","blanc_cavalier","blanc_tour"],
        ]


# ═══════════════════════════════════════════════════════════════════
#  NOTATION ALGÉBRIQUE
# ═══════════════════════════════════════════════════════════════════

class Notation:
    """Construit les chaînes de notation algébrique pour chaque coup."""

    @staticmethod
    def build(board: Board, src: Square, dst: Square,
              ep: Optional[Square],
              promotion: Optional[PieceType] = None) -> str:
        piece = board[src[0]][src[1]]
        pt    = piece_type(piece)

        # Roque
        castle = is_castling_move(board, src, dst)
        if castle == "kingside":
            return "O-O"
        if castle == "queenside":
            return "O-O-O"

        sym = PIECE_SYMBOLS.get(piece, "?")
        cap = "x" if (board[dst[0]][dst[1]]
                       or is_en_passant_move(board, src, dst, ep)) else ""
        alg = sq_to_alg(*dst)
        ep_suffix   = " e.p." if is_en_passant_move(board, src, dst, ep) else ""
        promo_suffix = f"={PIECE_SYMBOLS.get(piece_color(piece).value+'_'+promotion.value,'?')}" \
                       if promotion else ""

        return f"{sym}{cap}{alg}{ep_suffix}{promo_suffix}"


# ═══════════════════════════════════════════════════════════════════
#  JOUEUR IA  (Minimax + Élagage Alpha-Bêta + MVV-LVA + Table de Transposition)
# ═══════════════════════════════════════════════════════════════════

class AIPlayer:

    _transposition_table: dict = {}

    @staticmethod
    def _move_priority(board: Board, src: Square, dst: Square) -> int:
        victim   = board[dst[0]][dst[1]]
        attacker = board[src[0]][src[1]]
        if victim:
            return (PIECE_VALUES[piece_type(victim)]
                    - PIECE_VALUES[piece_type(attacker)] // 10)
        return 0

    @classmethod
    def _ordered_moves(cls, board: Board, moves: list[Move]) -> list[Move]:
        return sorted(moves,
                      key=lambda m: cls._move_priority(board, m[0], m[1]),
                      reverse=True)

    @staticmethod
    def _evaluate(board: Board) -> int:
        """Score positif = avantage des Noirs (l'IA joue les Noirs)."""
        score = 0
        for r in range(8):
            for c in range(8):
                p = board[r][c]
                if not p:
                    continue
                color  = piece_color(p)
                pt     = piece_type(p)
                pst_r  = r if color == Color.BLACK else 7 - r
                value  = PIECE_VALUES[pt] + _PST[pt][pst_r][c]
                score += value if color == Color.BLACK else -value
        return score

    @classmethod
    def _minimax(cls, board: Board, depth: int,
                 alpha: int, beta: int, maximizing: bool,
                 ep: Optional[Square], castling: dict) -> tuple[int, Optional[Move]]:

        key    = (tuple(tuple(r) for r in board), maximizing, ep)
        cached = cls._transposition_table.get(key)
        if cached and cached[0] >= depth:
            return cached[1], cached[2]

        color = Color.BLACK if maximizing else Color.WHITE
        moves = Engine.all_legal_moves(board, color, ep, castling)

        if depth == 0 or not moves:
            score = ((10_000 if maximizing else -10_000)
                     if (not moves and Engine.is_check(board, color))
                     else cls._evaluate(board))
            cls._transposition_table[key] = (depth, score, None)
            return score, None

        moves     = cls._ordered_moves(board, moves)
        best_move: Optional[Move] = None

        if maximizing:
            best_val = -99_999
            for src, dst in moves:
                tmp_b = copy.deepcopy(board)
                tmp_c = copy.deepcopy(castling)
                nep   = Engine.apply_move(tmp_b, src, dst, ep, tmp_c,
                                          promotion=PieceType.QUEEN)
                val, _ = cls._minimax(tmp_b, depth - 1, alpha, beta, False, nep, tmp_c)
                if val > best_val:
                    best_val  = val
                    best_move = (src, dst)
                alpha = max(alpha, val)
                if beta <= alpha:
                    break
        else:
            best_val = 99_999
            for src, dst in moves:
                tmp_b = copy.deepcopy(board)
                tmp_c = copy.deepcopy(castling)
                nep   = Engine.apply_move(tmp_b, src, dst, ep, tmp_c,
                                          promotion=PieceType.QUEEN)
                val, _ = cls._minimax(tmp_b, depth - 1, alpha, beta, True, nep, tmp_c)
                if val < best_val:
                    best_val  = val
                    best_move = (src, dst)
                beta = min(beta, val)
                if beta <= alpha:
                    break

        cls._transposition_table[key] = (depth, best_val, best_move)
        return best_val, best_move

    @classmethod
    def best_move(cls, board: Board, ep: Optional[Square],
                  castling: dict, depth: int = AI_DEPTH) -> Optional[Move]:
        cls._transposition_table = {}
        _, move = cls._minimax(copy.deepcopy(board), depth,
                               -99_999, 99_999, True, ep, copy.deepcopy(castling))
        return move


# ═══════════════════════════════════════════════════════════════════
#  ÉTAT DE LA PARTIE
# ═══════════════════════════════════════════════════════════════════

@dataclass
class GameState:
    board:        Board                          = field(default_factory=Engine.initial_board)
    castling:     dict                           = field(default_factory=Engine.default_castling)
    turn:         Color                          = Color.WHITE
    en_passant:   Optional[Square]               = None
    in_check:     bool                           = False
    checkmate:    bool                           = False
    stalemate:    bool                           = False
    selected:     Optional[Square]               = None
    legal_moves:  list[Square]                   = field(default_factory=list)
    last_move:    Optional[tuple[Square, Square]]= None
    move_history: list[str]                      = field(default_factory=list)
    # Mode de jeu
    mode:         GameMode                       = GameMode.VS_AI
    # État de la promotion
    pending_promotion: Optional[tuple[Square, Square]] = None   # (src, dst) en attente de choix
    # État de l'IA
    ia_thinking:  bool                           = False
    ia_result:    list                           = field(default_factory=lambda: [None])
    ia_start:     float                          = field(default_factory=time.time)
    think_dots:   int                            = 0

    def reset(self, mode: "GameMode | None" = None) -> None:
        kept_mode = mode if mode is not None else self.mode
        self.__init__()  # type: ignore[misc]
        self.mode = kept_mode

    # ── Mise à jour après un coup ───────────────────────────────────

    def _after_move(self) -> None:
        self.in_check = Engine.is_check(self.board, self.turn)
        if not Engine.has_legal_move(self.board, self.turn, self.en_passant, self.castling):
            self.checkmate = self.in_check
            self.stalemate = not self.in_check

    # ── Application des coups ─────────────────────────────────────

    def _commit_move(self, src: Square, dst: Square,
                     promotion: PieceType = PieceType.QUEEN) -> None:
        """Applique le coup, l'enregistre, change de tour et met à jour l'état."""
        notation         = Notation.build(self.board, src, dst, self.en_passant, promotion
                                          if is_promotion_move(self.board, src, dst) else None)
        self.en_passant  = Engine.apply_move(self.board, src, dst,
                                             self.en_passant, self.castling, promotion)
        self.last_move   = (src, dst)
        self.turn        = self.turn.opponent
        self.selected    = None
        self.legal_moves = []
        self.move_history.append(notation)
        self._after_move()

    def apply_human_move(self, dst: Square) -> None:
        src = self.selected
        assert src is not None

        if is_promotion_move(self.board, src, dst):
            # Suspendre – attendre le choix de pièce du joueur
            self.pending_promotion = (src, dst)
            return

        self._commit_move(src, dst)
        if self.mode == GameMode.VS_AI and not self.checkmate and not self.stalemate:
            self._demarrer_ia()

    def resolve_promotion(self, chosen: PieceType) -> None:
        """Appelée quand le joueur choisit sa pièce de promotion."""
        assert self.pending_promotion is not None
        src, dst = self.pending_promotion
        self.pending_promotion = None
        self._commit_move(src, dst, promotion=chosen)
        if self.mode == GameMode.VS_AI and not self.checkmate and not self.stalemate:
            self._demarrer_ia()

    def apply_ai_move(self, move: Move) -> None:
        src, dst = move
        self.ia_thinking = False
        self._commit_move(src, dst, promotion=PieceType.QUEEN)  # AI always promotes to queen

    # ── Interaction joueur ──────────────────────────────────────────

    def select_square(self, r: int, c: int) -> None:
        """Gère un clic sur le plateau pendant le tour du joueur."""
        if self.selected:
            if (r, c) in self.legal_moves:
                self.apply_human_move((r, c))
            elif self.board[r][c] and piece_color(self.board[r][c]) == self.turn:
                self.selected    = (r, c)
                self.legal_moves = Engine.legal_moves(
                    self.board, r, c, self.en_passant, self.castling)
            else:
                self.selected    = None
                self.legal_moves = []
        else:
            if self.board[r][c] and piece_color(self.board[r][c]) == self.turn:
                self.selected    = (r, c)
                self.legal_moves = Engine.legal_moves(
                    self.board, r, c, self.en_passant, self.castling)

    # ── Thread IA ────────────────────────────────────────────────────

    def _demarrer_ia(self) -> None:
        self.ia_thinking  = True
        self.ia_result[0] = None
        self.ia_start     = time.time()
        threading.Thread(
            target=self._thread_ia,
            args=(copy.deepcopy(self.board), self.en_passant,
                  copy.deepcopy(self.castling)),
            daemon=True,
        ).start()

    def _thread_ia(self, board: Board, ep: Optional[Square], castling: dict) -> None:
        self.ia_result[0] = AIPlayer.best_move(board, ep, castling)

    def poll_ai(self) -> None:
        """Récupère le résultat de l'IA dès qu'il est disponible (appelée à chaque image)."""
        if self.ia_thinking and self.ia_result[0] is not None:
            self.apply_ai_move(self.ia_result[0])
            self.ia_result[0] = None


# ═══════════════════════════════════════════════════════════════════
#  PROMOTION POPUP
# ═══════════════════════════════════════════════════════════════════

class PromotionPopup:
    """
    Affiche un écran centré permettant au joueur de choisir sa pièce de promotion.
    Retourne le PieceType choisi au clic, ou None.
    """

    POPUP_W = 280
    POPUP_H = 100

    def __init__(self, screen: pygame.Surface,
                 piece_images: dict[str, pygame.Surface],
                 color: Color) -> None:
        self.screen       = screen
        self.piece_images = piece_images
        self.color        = color
        self._rects: list[tuple[pygame.Rect, PieceType]] = []

    def draw(self) -> None:
        sw, sh = self.screen.get_size()
        px = (sw - self.POPUP_W) // 2
        py = (sh - self.POPUP_H) // 2

        # Dark overlay
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        # Popup box
        pygame.draw.rect(self.screen, C["promo_bg"],
                         (px, py, self.POPUP_W, self.POPUP_H), border_radius=6)
        pygame.draw.rect(self.screen, C["gold"],
                         (px, py, self.POPUP_W, self.POPUP_H), 2, border_radius=6)

        # Titre
        font  = pygame.font.SysFont("Georgia", 14)
        title = font.render("Choisir la pièce de promotion", True, C["gold2"])
        self.screen.blit(title, (px + self.POPUP_W // 2 - title.get_width() // 2,
                                 py + 6))

        # Piece buttons
        cell_w = self.POPUP_W // len(PROMOTION_TYPES)
        self._rects = []
        mx, my = pygame.mouse.get_pos()

        for i, pt in enumerate(PROMOTION_TYPES):
            rx = px + i * cell_w
            ry = py + 28
            rw, rh = cell_w, self.POPUP_H - 34
            rect = pygame.Rect(rx, ry, rw, rh)
            self._rects.append((rect, pt))

            hover = rect.collidepoint(mx, my)
            bg    = C["promo_hover"] if hover else C["promo_bg"]
            pygame.draw.rect(self.screen, bg, rect, border_radius=4)
            pygame.draw.rect(self.screen, C["panel_line"], rect, 1, border_radius=4)

            code = self.color.value + "_" + pt.value
            img  = self.piece_images.get(code)
            if img:
                scaled = pygame.transform.smoothscale(img, (rw - 8, rh - 8))
                self.screen.blit(scaled, (rx + 4, ry + 4))

    def handle_click(self, pos: tuple[int, int]) -> Optional[PieceType]:
        for rect, pt in self._rects:
            if rect.collidepoint(pos):
                return pt
        return None


# ═══════════════════════════════════════════════════════════════════
#  RENDU GRAPHIQUE
# ═══════════════════════════════════════════════════════════════════

class Renderer:

    def __init__(self, screen: pygame.Surface,
                 piece_images: dict[str, pygame.Surface]) -> None:
        self.screen       = screen
        self.piece_images = piece_images
        self._initialiser_polices()
        self._promo_popup: Optional[PromotionPopup] = None

    def _initialiser_polices(self) -> None:
        try:
            self.f_title  = pygame.font.SysFont("Georgia",     22, bold=True)
            self.f_coord  = pygame.font.SysFont("Georgia",     13)
            self.f_move   = pygame.font.SysFont("Courier New", 13)
            self.f_status = pygame.font.SysFont("Georgia",     20, bold=True)
            self.f_big    = pygame.font.SysFont("Georgia",     30, bold=True)
        except Exception:
            fb = pygame.font.SysFont(None, 18)
            self.f_title = self.f_coord = self.f_move = self.f_status = self.f_big = fb

    # ── Plateau ───────────────────────────────────────────────────────

    def draw_board(self) -> None:
        self.screen.fill(C["bg"])
        border = pygame.Rect(BOARD_X - 3, BOARD_Y - 3, BOARD_SIZE + 6, BOARD_SIZE + 6)
        pygame.draw.rect(self.screen, C["gold"], border, 2, border_radius=2)

        for r in range(8):
            for c in range(8):
                col = C["sq_light"] if (r + c) % 2 == 0 else C["sq_dark"]
                pygame.draw.rect(self.screen, col,
                                 (BOARD_X + c * SQ, BOARD_Y + r * SQ, SQ, SQ))

        for c in range(8):
            lbl = self.f_coord.render("abcdefgh"[c], True, C["coord"])
            self.screen.blit(lbl, (BOARD_X + c * SQ + SQ // 2 - lbl.get_width() // 2,
                                   BOARD_Y + BOARD_SIZE + 5))
        for r in range(8):
            lbl = self.f_coord.render(str(8 - r), True, C["coord"])
            self.screen.blit(lbl, (BOARD_X - lbl.get_width() - 6,
                                   BOARD_Y + r * SQ + SQ // 2 - lbl.get_height() // 2))

    def draw_highlights(self, gs: GameState) -> None:
        def afficher_alpha(r: int, c: int, rgba: tuple) -> None:
            s = pygame.Surface((SQ, SQ), pygame.SRCALPHA)
            s.fill(rgba)
            self.screen.blit(s, (BOARD_X + c * SQ, BOARD_Y + r * SQ))

        # Last move
        if gs.last_move:
            for sq in gs.last_move:
                afficher_alpha(sq[0], sq[1], (*C["green"], 80))

        # Selected square
        if gs.selected:
            afficher_alpha(gs.selected[0], gs.selected[1], (*C["gold"], 120))
            for r, c in gs.legal_moves:
                cx = BOARD_X + c * SQ + SQ // 2
                cy = BOARD_Y + r * SQ + SQ // 2
                # Cercle autour des cases occupées (captures), point sur cases vides
                if gs.board[r][c]:
                    pygame.draw.circle(self.screen, C["gold"], (cx, cy), SQ // 2 - 3, 3)
                else:
                    pygame.draw.circle(self.screen, C["gold"], (cx, cy), 8)

        # Roi en échec
        if gs.in_check and not gs.checkmate:
            pos = Engine.find_king(gs.board, gs.turn)
            if pos:
                afficher_alpha(pos[0], pos[1], (*C["red"], 140))

    def draw_pieces(self, board: Board) -> None:
        for r in range(8):
            for c in range(8):
                p = board[r][c]
                if p and p in self.piece_images:
                    x = BOARD_X + c * SQ + PIECE_OFFSET
                    y = BOARD_Y + r * SQ + PIECE_OFFSET
                    self.screen.blit(self.piece_images[p], (x, y))

    # ── Panneau latéral ────────────────────────────────────────────

    def draw_panel(self, gs: GameState, elapsed: float) -> None:
        px = BOARD_X + BOARD_SIZE + MARGIN
        pw = PANEL_W - 10
        y  = 18

        self.screen.fill(C["panel_bg"], pygame.Rect(px, 0, pw, WIN_H))
        pygame.draw.line(self.screen, C["gold"],
                         (px, BOARD_Y), (px, BOARD_Y + BOARD_SIZE), 1)

        def ligne(text: str, font: pygame.font.Font,
                 color: tuple, center: bool = True, indent: int = 0) -> None:
            nonlocal y
            surf = font.render(text, True, color)
            x    = (px + pw // 2 - surf.get_width() // 2) if center else (px + 10 + indent)
            self.screen.blit(surf, (x, y))
            y += surf.get_height() + 4

        def ligne_h() -> None:
            nonlocal y
            pygame.draw.line(self.screen, C["panel_line"],
                             (px + 8, y), (px + pw - 8, y))
            y += 12

        # Titre
        ligne("ÉCHECS",          self.f_title, C["gold"])
        ligne(gs.mode.value,     self.f_coord,  C["dim"])
        y += 4
        ligne_h()

        # Status
        status_text, status_color = self._status_info(gs)
        ligne(status_text, self.f_status, status_color)
        if gs.ia_thinking and elapsed > 0:
            ligne(f"{elapsed:.1f}s", self.f_coord, C["dim"])
        if gs.pending_promotion:
            ligne("Choisir la promotion ↓", self.f_coord, C["gold2"])
        y += 2
        ligne_h()

        # ── Légende des coups spéciaux ───────────────────────────────
        ligne("Coups spéciaux", self.f_coord, C["dim"], center=False)
        y += 2
        for etiquette in ("O-O   Petit roque",
                          "O-O-O  Grand roque",
                          "e.p.   En passant",
                          "=♕    Promotion"):
            ligne(etiquette, self.f_move, C["dim"], center=False, indent=4)
        y += 2
        ligne_h()

        # ── Historique des coups ─────────────────────────────────────
        ligne("Historique", self.f_coord, C["dim"], center=False)
        y += 2

        col_w    = (pw - 30) // 2
        header_w = self.f_coord.render("Blancs", True, (200, 180, 130))
        header_b = self.f_coord.render("Noirs",  True, C["grey"])
        self.screen.blit(header_w, (px + 22, y))
        self.screen.blit(header_b, (px + 22 + col_w + 10, y))
        y += header_w.get_height() + 4

        pairs = [
            (i // 2 + 1,
             gs.move_history[i]   if i     < len(gs.move_history) else "",
             gs.move_history[i+1] if i + 1 < len(gs.move_history) else "")
            for i in range(0, len(gs.move_history), 2)
        ]
        for num, w_mv, b_mv in pairs[-10:]:
            n_s = self.f_move.render(f"{num}.", True, C["dim"])
            w_s = self.f_move.render(w_mv,      True, C["text"])
            b_s = self.f_move.render(b_mv,      True, C["grey"])
            self.screen.blit(n_s, (px + 4,               y))
            self.screen.blit(w_s, (px + 22,              y))
            self.screen.blit(b_s, (px + 22 + col_w + 10, y))
            y += w_s.get_height() + 2

        y += 6
        ligne_h()

        for raccourci in ("R  –  Rejouer", "Échap  –  Quitter"):
            ligne(raccourci, self.f_coord, C["dim"])

        # ── Écran de fin de partie ───────────────────────────────────
        if gs.checkmate or gs.stalemate:
            ov = pygame.Surface((pw, 70), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 210))
            self.screen.blit(ov, (px, WIN_H // 2 - 35))
            msg = self.f_big.render(status_text, True, C["gold2"])
            self.screen.blit(msg, (px + pw // 2 - msg.get_width() // 2,
                                   WIN_H // 2 - msg.get_height() // 2))
            hint = self.f_coord.render("Appuyez sur R pour rejouer", True, C["dim"])
            self.screen.blit(hint, (px + pw // 2 - hint.get_width() // 2,
                                    WIN_H // 2 + 24))

    def _status_info(self, gs: GameState) -> tuple[str, tuple]:
        if gs.checkmate:
            if gs.mode == GameMode.VS_AI:
                winner = "Noirs (IA)" if gs.turn == Color.WHITE else "Blancs (Vous)"
            else:
                winner = "Noirs" if gs.turn == Color.WHITE else "Blancs"
            return f"☆ {winner} gagnent !", C["gold2"]
        if gs.stalemate:
            return "½  Pat – Égalité", C["dim"]
        if gs.ia_thinking:
            return f"IA réfléchit{'.' * (gs.think_dots % 4)}", C["blue"]
        if gs.turn == Color.WHITE:
            label = "▶  Blancs" if gs.mode == GameMode.VS_HUMAN else "▶  Votre tour"
            if gs.in_check:
                return label + "  ÉCHEC !", C["red"]
            return label, C["gold2"]
        label = "▶  Noirs" if gs.mode == GameMode.VS_HUMAN else "▶  Tour IA"
        if gs.in_check:
            return label + "  ÉCHEC !", C["red"]
        return label, C["grey"]

    # ── Image complète ───────────────────────────────────────────────

    def render(self, gs: GameState,
               promo_popup: Optional[PromotionPopup] = None) -> None:
        elapsed = time.time() - gs.ia_start if gs.ia_thinking else 0.0
        self.draw_board()
        self.draw_highlights(gs)
        self.draw_pieces(gs.board)
        self.draw_panel(gs, elapsed)
        if promo_popup:
            promo_popup.draw()
        pygame.display.flip()


# ═══════════════════════════════════════════════════════════════════
#  CHARGEMENT DES IMAGES
# ═══════════════════════════════════════════════════════════════════

def load_piece_images() -> dict[str, pygame.Surface]:
    images: dict[str, pygame.Surface] = {}
    codes = [f"{c.value}_{t.value}" for c in Color for t in PieceType]
    for code in codes:
        for ext in PIECE_EXTENSIONS:
            path = os.path.join(IMAGES_DIR, code + ext)
            if os.path.isfile(path):
                try:
                    img = pygame.image.load(path).convert_alpha()
                    images[code] = pygame.transform.smoothscale(img, (PIECE_SZ, PIECE_SZ))
                    break
                except pygame.error as e:
                    print(f"[Erreur image] {path}: {e}")
    missing = [c for c in codes if c not in images]
    if missing:
        print(f"[Avertissement] Images manquantes : {missing}")
    return images


# ═══════════════════════════════════════════════════════════════════
#  ÉCRAN DE MENU
# ═══════════════════════════════════════════════════════════════════

class MenuScreen:
    """
    Menu plein écran affiché au démarrage et après chaque partie.
    Retourne le GameMode choisi quand le joueur clique sur un bouton.
    """

    BTN_W = 260
    BTN_H = 60
    GAP   = 20

    def __init__(self, screen: pygame.Surface,
                 piece_images: dict[str, pygame.Surface]) -> None:
        self.screen       = screen
        self.piece_images = piece_images
        try:
            self.f_title  = pygame.font.SysFont("Georgia", 48, bold=True)
            self.f_sub    = pygame.font.SysFont("Georgia", 18)
            self.f_btn    = pygame.font.SysFont("Georgia", 22, bold=True)
            self.f_hint   = pygame.font.SysFont("Georgia", 13)
        except Exception:
            fb = pygame.font.SysFont(None, 24)
            self.f_title = self.f_sub = self.f_btn = self.f_hint = fb
        self._buttons: list[tuple[pygame.Rect, GameMode]] = []

    def _build_buttons(self) -> None:
        sw, sh  = self.screen.get_size()
        total_h = len(GameMode) * (self.BTN_H + self.GAP) - self.GAP
        start_y = sh // 2 - total_h // 2 + 40
        self._buttons = []
        for i, mode in enumerate(GameMode):
            rx = sw // 2 - self.BTN_W // 2
            ry = start_y + i * (self.BTN_H + self.GAP)
            self._buttons.append((pygame.Rect(rx, ry, self.BTN_W, self.BTN_H), mode))

    def run(self) -> GameMode:
        """Boucle bloquante – retourne quand un mode est sélectionné."""
        self._build_buttons()
        clock = pygame.time.Clock()

        while True:
            clock.tick(60)
            mx, my = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN:
                    for rect, mode in self._buttons:
                        if rect.collidepoint(event.pos):
                            return mode

            self._draw(mx, my)

    def _draw(self, mx: int, my: int) -> None:
        sw, sh = self.screen.get_size()
        self.screen.fill(C["bg"])

        # Motif d'échiquier décoratif en arrière-plan
        sq = 40
        for r in range(sh // sq + 1):
            for c in range(sw // sq + 1):
                if (r + c) % 2 == 0:
                    s = pygame.Surface((sq, sq), pygame.SRCALPHA)
                    s.fill((*C["sq_dark"], 60))
                    self.screen.blit(s, (c * sq, r * sq))

        # Cadre doré
        pygame.draw.rect(self.screen, C["gold"],
                         pygame.Rect(20, 20, sw - 40, sh - 40), 1, border_radius=6)

        # Titre
        title = self.f_title.render("ÉCHECS", True, C["gold"])
        self.screen.blit(title, (sw // 2 - title.get_width() // 2, sh // 4 - 40))

        # Sous-titre
        sub = self.f_sub.render("Choisissez un mode de jeu", True, C["dim"])
        self.screen.blit(sub, (sw // 2 - sub.get_width() // 2, sh // 4 + title.get_height() - 20))

        # Boutons
        for rect, mode in self._buttons:
            hover = rect.collidepoint(mx, my)
            bg    = C["gold"] if hover else C["panel_bg"]
            tc    = C["bg"]   if hover else C["gold2"]
            border_col = C["gold2"] if hover else C["gold"]

            pygame.draw.rect(self.screen, bg,         rect, border_radius=8)
            pygame.draw.rect(self.screen, border_col, rect, 2, border_radius=8)

            lbl = self.f_btn.render(mode.value, True, tc)
            self.screen.blit(lbl, (rect.centerx - lbl.get_width() // 2,
                                   rect.centery - lbl.get_height() // 2))

        # Indication touche Échap
        hint = self.f_hint.render("Échap  –  Quitter", True, C["dim"])
        self.screen.blit(hint, (sw // 2 - hint.get_width() // 2, sh - 40))

        pygame.display.flip()


# ═══════════════════════════════════════════════════════════════════
#  APPLICATION
# ═══════════════════════════════════════════════════════════════════

class App:

    def __init__(self) -> None:
        pygame.init()
        self.screen       = pygame.display.set_mode((WIN_W, WIN_H))
        pygame.display.set_caption("Échecs")
        self.clock        = pygame.time.Clock()
        self.piece_images = load_piece_images()
        self.renderer     = Renderer(self.screen, self.piece_images)
        self.menu         = MenuScreen(self.screen, self.piece_images)
        self.gs:    GameState              = GameState()
        self._promo_popup: Optional[PromotionPopup] = None
        self._tick        = 0

    def run(self) -> None:
        """Boucle principale : afficher le menu, jouer, recommencer."""
        while True:
            mode = self.menu.run()
            self._start_game(mode)
            self._game_loop()

    def _start_game(self, mode: GameMode) -> None:
        self.gs = GameState(mode=mode)
        self._promo_popup = None
        self._tick        = 0
        pygame.display.set_caption(f"Échecs – {mode.value}")

    def _game_loop(self) -> None:
        while True:
            self.clock.tick(60)
            self._tick += 1

            self.gs.poll_ai()
            if self._tick % 30 == 0 and self.gs.ia_thinking:
                self.gs.think_dots += 1

            # Cycle de vie du popup de promotion
            if self.gs.pending_promotion and self._promo_popup is None:
                promo_color = self.gs.turn.opponent   # couleur du pion qui vient de se promouvoir
                self._promo_popup = PromotionPopup(
                    self.screen, self.piece_images, promo_color)
            if not self.gs.pending_promotion:
                self._promo_popup = None

            action = self._handle_events()
            if action == "menu":
                return   # retour au menu

            self.renderer.render(self.gs, self._promo_popup)

    def _handle_events(self) -> Optional[str]:
        for event in pygame.event.get():
            match event.type:
                case pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                case pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return "menu"        # Échap → retour au menu
                    if event.key == pygame.K_r:
                        self.gs.reset()      # R → recommencer le même mode
                        self._promo_popup = None

                case pygame.MOUSEBUTTONDOWN:
                    self._handle_click(event.pos)
        return None

    def _handle_click(self, pos: tuple[int, int]) -> None:
        gs = self.gs

        # Le popup de promotion est prioritaire
        if self._promo_popup is not None:
            chosen = self._promo_popup.handle_click(pos)
            if chosen is not None:
                gs.resolve_promotion(chosen)
            return

        # En mode VS_IA, seul le joueur Blanc peut cliquer
        if gs.mode == GameMode.VS_AI:
            if gs.turn != Color.WHITE or gs.checkmate or gs.stalemate or gs.ia_thinking:
                return
        else:
            # En mode 2 joueurs, les deux camps peuvent cliquer (sauf fin de partie)
            if gs.checkmate or gs.stalemate:
                return

        c = (pos[0] - BOARD_X) // SQ
        r = (pos[1] - BOARD_Y) // SQ
        if on_board(r, c):
            gs.select_square(r, c)


# ═══════════════════════════════════════════════════════════════════
#  POINT D'ENTRÉE
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    App().run()