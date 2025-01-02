import org.openqa.selenium.By;
import org.openqa.selenium.JavascriptExecutor;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.interactions.Actions;
import org.testng.annotations.Test;

import java.util.concurrent.TimeUnit;

public class DragandDrop {


    @Test
    public void doubleclickexample() {
        System.setProperty("webdriver.chrome.driver", "D:\\Intellij\\chromedriver.exe");

        // Create a new instance of the Firefox driver
        WebDriver driver = new ChromeDriver();

        // Launch the URL
        driver.get("https://demoqa.com/droppable/");
        System.out.println("demoqa webpage displayed");

        //Maximise browser window
        driver.manage().window().maximize();

        JavascriptExecutor js = (JavascriptExecutor) driver;
        js.executeScript("window.scrollBy(0,150)");
        driver.manage().timeouts().implicitlyWait(10000, TimeUnit.MILLISECONDS);

        //Actions class method to drag and drop
        Actions builder = new Actions(driver);

        WebElement from = driver.findElement(By.id("draggable"));

        WebElement to = driver.findElement(By.id("droppable"));
        //Perform drag and drop
        builder.dragAndDrop(from, to).perform();

        //verify text changed in to 'Drop here' box
        String textTo = to.getText();

        if (textTo.equals("Dropped!")) {
            System.out.println("PASS: Source is dropped to target as expected");
        } else {
            System.out.println("FAIL: Source couldn't be dropped to target as expected");
        }

        // driver.close();
    }
}
