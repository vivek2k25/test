import org.openqa.selenium.By;
import org.openqa.selenium.Keys;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.testng.annotations.Test;

import java.awt.*;

public class RobotClass {

    private static final Logger log = LoggerFactory.getLogger(RobotClass.class);

    @Test
    public void robotclassexample()
    {
        WebDriver driver;
        System.setProperty("webdriver.chrome.driver", "D:\\Intellij\\chromedriver.exe");
        ChromeOptions options = new ChromeOptions();
        options.addArguments("headless");
        driver = new ChromeDriver(options);



        // Create a new instance of the Firefox driver
       // WebDriver driver = new ChromeDriver();


        // Launch the URL
        driver.get("https://demoqa.com/upload-download");
        System.out.println("demoqa webpage displayed");
        log.info("tttttttttttttt");

        //Maximise browser window
        driver.manage().window().maximize();

        try {
            Thread.sleep(2000);
        } catch (InterruptedException e) {
            throw new RuntimeException(e);
        }

        WebElement webElement = driver.findElement(By.id("browseFile"));
        //click  Browse button
        webElement.sendKeys(Keys.ENTER);

    }

}
