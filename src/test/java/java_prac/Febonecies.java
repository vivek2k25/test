package java_prac;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.testng.annotations.Test;

public class Febonecies {

    private static final Logger log = LoggerFactory.getLogger(Febonecies.class);

    @Test
    public void feb()
    {
        int a =0;
        int b =1;
        int c;

        for(int i =1;i<10;i++)
        {

            c=a+b;
            if (c>20)

                break;

            log.info("Numer is " + c);
            System.out.println("Number is " + c);

            a=b;
            b=c;
        }


    }

    @Test
    public void anotherway()
    {
       // public static void main(String[] args)
        { int n = 10, a = 0, b = 1;
            System.out.print("Fibonacci Series: " + a + " " + b);
            for (int i = 2; i < n; i++)
            { int c = a + b;
                if(c>12)
                    break;
                System.out.print(" " + c); a = b; b = c; }
        }
    }
}

