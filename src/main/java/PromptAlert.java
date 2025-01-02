import org.openqa.selenium.*;
import org.openqa.selenium.chrome.ChromeDriver;
import org.testng.annotations.Test;

public class PromptAlert {


    @Test
    public void promptalert()
 {
     System.setProperty("webdriver.chrome.driver", "D:\\Intellij\\chromedriver.exe");
    WebDriver driver = new ChromeDriver();
   driver.get("https://demoqa.com/alerts");
   driver.manage().window().maximize();
    // This step will result in an alert on screen
    WebElement element = driver.findElement(By.id("promtButton"));
   ((JavascriptExecutor) driver).executeScript("arguments[0].click()", element);
    Alert promptAlert  = driver.switchTo().alert();
    String alertText = promptAlert.getText();
   System.out.println("Alert text is " + alertText);
    //Send some text to the alert
   promptAlert.sendKeys("Test User");
   System.out.println("Text entered");
   promptAlert.accept();
}

}