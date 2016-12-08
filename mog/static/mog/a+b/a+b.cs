using System;

namespace MyNamespace {
	class Program {
		public static void Main(string[] argv) {
			string[] line = Console.ReadLine().Split(' ');
			int a = int.Parse(line[0]);
			int b = int.Parse(line[1]);
			Console.WriteLine(a + b);
		}
	}
}
