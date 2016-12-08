open System

let add a b = a + b

let line = Console.ReadLine().Split(' ')
let a = Int32.Parse(line.[0])
let b = Int32.Parse(line.[1])
Console.WriteLine(add a b)
