import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.testng.Assert;
import org.testng.annotations.Test;
import org.testng.log4testng.Logger;

import java.util.List;

public class OtherCommands {

    //   public class ChromeHeadless {
    WebDriver driver;


    @Test
    public void otherseleniumcommands() throws InterruptedException {
//WebDriverManager.chromedriver().setup();


        System.setProperty("webdriver.chrome.driver", "D:\\Intellij\\chromedriver.exe");
        ChromeOptions options = new ChromeOptions();
        options.addArguments("chrome");
        driver = new ChromeDriver(options);
        driver.get("https://demoqa.com/text-box/");
        driver.manage().window().maximize();

        System.out.println("Title is: " + driver.getTitle());
      //  Assert.assertEquals(driver.getTitle(), "Most Reliable App & Cross Browser Testing Platform | BrowserStack");




     //   WebElement classlist = driver.findElement(By.xpath("//input[@class=' mr-sm-2 form-control']"));
       // System.out.println("Class name print here   === " + classlist.getClass());



       /*List<WebElement> classlists = driver.findElements(By.xpath("//input[@class=' mr-sm-2 form-control']"));

       if(classlists.size()!=0)
       {
           System.out.println(classlists.size() + " Elements found by TagName as input \n");

           for(WebElement inputElement : classlists)
           {
               System.out.println(inputElement.getAttribute("placeholder"));
           }
       }

*/

       List<WebElement> linkdata = driver.findElements(By.tagName("href"));
       System.out.println("Get the link counts == " + linkdata.size());

       if (linkdata.size()!=0)
       {
           System.out.println("Link count is greater than 0 ");

           for (WebElement link :linkdata)
           {
               System.out.println("System link text = " + link.getText());
           }


       }






    }
}
