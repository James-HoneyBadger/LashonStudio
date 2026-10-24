(* MathUtils — Pascal-Like via Lashon
   Collection of common mathematical computations.
   Demonstrates: FUNCTION declarations, local VARs, CONST blocks *)

PROGRAM MathUtils;

CONST
  Pi      = 3;        (* integer approximation for demo *)
  E       = 2;
  MaxIter = 100;

(* ── Integer power ─────────────────────────────────────── *)
FUNCTION Power(base, exp : INTEGER) : INTEGER;
VAR
  result : INTEGER;
  i      : INTEGER;
BEGIN
  result := 1;
  i      := 0;
  WHILE i < exp DO
  BEGIN
    result := result * base;
    i      := i + 1;
  END;
  Power := result;
END;

(* ── Greatest common divisor (Euclidean) ─────────────────── *)
FUNCTION GCD(a, b : INTEGER) : INTEGER;
VAR
  temp : INTEGER;
BEGIN
  WHILE b <> 0 DO
  BEGIN
    temp := b;
    b    := a MOD b;
    a    := temp;
  END;
  GCD := a;
END;

(* ── Least common multiple ──────────────────────────────── *)
FUNCTION LCM(a, b : INTEGER) : INTEGER;
BEGIN
  LCM := (a * b) DIV GCD(a, b);
END;

(* ── Check primality ─────────────────────────────────────── *)
FUNCTION IsPrime(n : INTEGER) : BOOLEAN;
VAR
  i       : INTEGER;
  is_prime : BOOLEAN;
BEGIN
  IF n < 2 THEN
    IsPrime := FALSE
  ELSE
  BEGIN
    is_prime := TRUE;
    i        := 2;
    WHILE i * i <= n DO
    BEGIN
      IF n MOD i = 0 THEN
        is_prime := FALSE;
      i := i + 1;
    END;
    IsPrime := is_prime;
  END;
END;

(* ── Main program ─────────────────────────────────────── *)
VAR
  x, y  : INTEGER;
  limit : INTEGER;
  i     : INTEGER;

BEGIN
  x := 48;
  y := 36;

  WriteLn('=== Math Utilities Demo ===');
  WriteLn();
  WriteLn('Power(2, 10) = ', Power(2, 10));
  WriteLn('GCD(', x, ', ', y, ')  = ', GCD(x, y));
  WriteLn('LCM(', x, ', ', y, ')  = ', LCM(x, y));
  WriteLn();

  limit := 30;
  Write('Primes up to ', limit, ': ');
  i := 2;
  WHILE i <= limit DO
  BEGIN
    IF IsPrime(i) THEN
      Write(i, ' ');
    i := i + 1;
  END;
  WriteLn();
END.
