import org.apache.commons.io.FileUtils;
import org.apache.log4j.LogManager;
import org.apache.log4j.Logger;
import org.openqa.selenium.*;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.testng.annotations.Test;

import javax.imageio.ImageIO;
import java.io.File;
import java.io.IOException;

public class TakesScreenshotsExamples {

    // private static Logger Log = Logger.getLogger(LogExample.class.getName());
    Logger logging = LogManager.getLogger(LogExample.class.getName());
    public WebDriver driver;

    @Test
    public void screenshotsexp() {

     //   WebDriver driver;
        //  DOMConfigurator.configure("log4j.xml");
        System.setProperty("webdriver.chrome.driver", "D:\\Intellij\\chromedriver.exe");
        ChromeOptions options = new ChromeOptions();
        options.addArguments("chrome");
        driver = new ChromeDriver(options);
        driver.get("https://demoqa.com/text-box/");
        driver.manage().window().maximize();
        logging.info("Window is maximize here ");

        File screenshots = ((TakesScreenshot)driver).getScreenshotAs(OutputType.FILE);

        String screenshotDirectory ="C:\\Users\\Vivek\\Vivek_Personal\\simulator\\untitled\\";

        String filedestination = screenshotDirectory + getClass() + "_" + System.currentTimeMillis() + ".png";

        try
        {
            FileUtils.copyFile(screenshots,new File(filedestination));
        } catch (IOException e) {
            throw new RuntimeException(e.getMessage());
        }

        System.out.println("Not closing the browser here");



    }




}
