(* Hello World — Pascal-Like via Lashon
   Demonstrates basic variable assignment and arithmetic.
   Run with: lashon repl configs/examples/pascal_like.yaml *)

PROGRAM HelloWorld;

VAR
  greeting : STRING;
  count     : INTEGER;
  message   : STRING;

BEGIN
  greeting := 'Hello';
  count    := 42;
  message  := 'Lashon Pascal demo';

  WriteLn(greeting, ', World!');
  WriteLn('Count = ', count);
  WriteLn('Message: ', message);
END.
