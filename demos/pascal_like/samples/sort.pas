(* Sorting — Pascal-Like via Lashon
   Bubble-sort demonstration with step-by-step output.
   Demonstrates: ARRAY OF, FOR loops, nested BEGIN..END, swapping *)

PROGRAM Sorting;

CONST
  N = 8;

VAR
  data  : ARRAY [1..N] OF INTEGER;
  i, j  : INTEGER;
  temp  : INTEGER;
  swaps : INTEGER;

BEGIN
  (* Initialise unsorted data *)
  data[1] := 64;
  data[2] := 34;
  data[3] := 25;
  data[4] := 12;
  data[5] := 22;
  data[6] := 11;
  data[7] := 90;
  data[8] := 42;

  WriteLn('=== Bubble Sort Demo ===');
  Write('Unsorted: ');
  FOR i := 1 TO N DO
    Write(data[i], ' ');
  WriteLn();

  swaps := 0;

  (* Bubble sort *)
  FOR i := 1 TO N - 1 DO
  BEGIN
    FOR j := 1 TO N - i DO
    BEGIN
      IF data[j] > data[j + 1] THEN
      BEGIN
        temp       := data[j];
        data[j]    := data[j + 1];
        data[j + 1] := temp;
        swaps      := swaps + 1;
      END;
    END;
  END;

  Write('Sorted:   ');
  FOR i := 1 TO N DO
    Write(data[i], ' ');
  WriteLn();

  WriteLn('Total swaps: ', swaps);
END.
