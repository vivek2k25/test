//public class SetExample {

    import java.util.Set;
import java.util.HashSet;
import java.util.Iterator;

    public class SetExample {
        public static void main(String[] args) {
            // Creating a Set of Strings
            Set<String> fruits = new HashSet<>();

            // Adding elements to the Set
            fruits.add("Apple");
            fruits.add("Banana");
            fruits.add("Cherry");
            fruits.add("Grapes");
            fruits.add("Papaya");
            fruits.add("Apple"); // Duplicate element, will not be added

            // Checking if the set contains "Apple"
            System.out.println("Contains Apple: " + fruits.contains("Apple"));

            // Removing "Banana" from the set
            fruits.remove("Banana");

            // Iterating over the set using enhanced for loop
            System.out.println("Fruits in the set:");
            for (String fruit : fruits) {
                System.out.println(fruit);
            }

            // Iterating over the set using Iterator
            System.out.println("Fruits in the set (using Iterator):");
            Iterator<String> iterator = fruits.iterator();
            while (iterator.hasNext()) {
                System.out.println(iterator.next());
            }

            // Printing the final state of the set
            System.out.println("Final Set: " + fruits);
        }
    }
