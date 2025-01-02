package java_prac;

//public class ReverseStringExample {
public class ReverseStringExample {
    public static void main(String[] args) {
        String original = "Hello, World";
        String reversed = reverseString(original);
        System.out.println("Original: " + original);
        System.out.println("Reversed: " + reversed);
    }

    public static String reverseString(String str) {
        if (str.isEmpty()) {
            return str;
        }
        return reverseString(str.substring(1)) + str.charAt(0);
    }
}
