import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.interactions.Actions;
import org.testng.Assert;
import org.testng.annotations.Test;

public class DoubleClick {


    @Test
    public void doubleclickexample() {
        System.setProperty("webdriver.chrome.driver", "D:\\Intellij\\chromedriver.exe");

        // Create a new instance of the Firefox driver
        WebDriver driver = new ChromeDriver();

        // Launch the URL
        driver.get("https://demoqa.com/buttons");
        System.out.println("demoqa webpage displayed");

        //Maximise browser window
        driver.manage().window().maximize();

        //Instantiate Action Class
        Actions actions = new Actions(driver);

        //Retrieve WebElement to perform right click
        WebElement btnElement = driver.findElement(By.id("doubleClickBtn"));

        //Right Click the button to display Context Menu&nbsp;
        actions.doubleClick(btnElement).perform();




        WebElement txt = driver.findElement(By.id("doubleClickMessage"));
        Assert.assertEquals(txt.getText(),"You have done a double click");
        System.out.println("Text afer double click is =="  + txt.getText());
        driver.quit();

    }

}