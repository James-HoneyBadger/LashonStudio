(* Fibonacci — Pascal-Like via Lashon
   Iterative Fibonacci using a WHILE loop.
   Demonstrates: VAR block, WHILE..DO, BEGIN..END blocks, WriteLn *)

PROGRAM Fibonacci;

VAR
  n     : INTEGER;
  a, b  : INTEGER;
  temp  : INTEGER;
  i     : INTEGER;

BEGIN
  n := 15;
  a := 0;
  b := 1;
  i := 0;

  WriteLn('Fibonacci sequence up to term ', n, ':');
  WriteLn('  F(0) = ', a);
  WriteLn('  F(1) = ', b);

  i := 2;
  WHILE i <= n DO
  BEGIN
    temp := a + b;
    a    := b;
    b    := temp;
    WriteLn('  F(', i, ') = ', b);
    i := i + 1;
  END;

  WriteLn('Done. F(', n, ') = ', b);
END.
