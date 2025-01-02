import org.openqa.selenium.By;
import org.openqa.selenium.Dimension;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.testng.Assert;
import org.testng.annotations.Test;

public class Checkboxes {


    @Test
    public void checboxexamples() throws InterruptedException {


        // Set up the ChromeDriver
        System.setProperty("webdriver.chrome.driver", "D:\\Intellij\\chromedriver.exe");
        WebDriver driver = new ChromeDriver();

        // Navigate to the practice form
        driver.get("https://demoqa.com/checkbox");

      //  Dimension targetSize = new Dimension(1024, 1024);
      //  driver.manage().window().setSize(targetSize);

        driver.manage().window().maximize();

        Thread.sleep(1000);

        // check the checkbox
     //  WebElement chk =  driver.findElement(By.id("hobbies-checkbox-1"));
       //chk.click();


     //  driver.findElement(By.xpath("//label[text()='Reading']")).click();

       WebElement chk =driver.findElement(By.xpath("//span[@class='rct-checkbox']"));
       boolean isselected =  chk.isSelected();

       if(isselected==false)
       {
           chk.click();
           System.out.println("check box is check by iD");
       }
       else
           System.out.println("Item not available");







        driver.navigate().to("https://demoqa.com/radio-button");

        // Validate the radio

        Thread.sleep(10000);

        WebElement radiobutton = driver.findElement(By.xpath("//div//input[@id='impressiveRadio']"));
        boolean rdbtn = radiobutton.isDisplayed();

      //  Assert.assertEquals(driver.getTitle(), "Most Reliable App & Cross Browser Testing Platform | BrowserStack");

      //  Assert.assertEquals(rdbtn,false,"radio button is displayed ");

        radiobutton.click();









    }

}
