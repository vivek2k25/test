package java_prac;

import org.testng.annotations.Test;

public class PrimeNumber {


    @Test
    public void findnumberisprime() {
        int num = 9;
        int temp = 0;

        for (int i = 2; i < num - 1; i++) {
            if (num % i == 0) {
                temp = temp + 1;
            }
        }

        if (temp > 0) {
            System.out.println("Number is not prime");
        } else
            System.out.println("Number is  prime");


    }

    @Test
    public void listofprimenumner() {
        {
            //int num = 9;
            int temp = 0;

            for (int num = 1; num <= 100; num++) {
                for (int i = 2; i < num - 1; i++) {
                    if (num % i == 0) {
                        temp = temp + 1;
                    }
                }

                if (temp ==0) {
                    System.out.println(num);
                } else
                    //System.out.println("Number is  prime");
                temp=0;

            }

        }
    }
}
