import org.apache.commons.io.FileUtils;
import org.apache.log4j.Logger;
import org.apache.log4j.PropertyConfigurator;
import org.openqa.selenium.By;
import org.openqa.selenium.OutputType;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.testng.annotations.Test;
import ru.yandex.qatools.ashot.AShot;
import ru.yandex.qatools.ashot.Screenshot;
import ru.yandex.qatools.ashot.shooting.ShootingStrategies;

import javax.imageio.ImageIO;
import java.io.File;
import java.io.IOException;

public class Fullscreen {

    WebDriver driver;
    static Logger logger = Logger.getLogger(ActionClass.class);


@Test

    public void fullscreenshot() throws IOException, InterruptedException {
        PropertyConfigurator.configure("src/main/resources/log4j.properties");
       // driver.get("https://demoqa.com");

        System.setProperty("webdriver.chrome.driver", "D:\\Intellij\\chromedriver.exe");
        ChromeOptions options = new ChromeOptions();
        options.addArguments("chrome");
        driver = new ChromeDriver(options);
        driver.get("https://demoqa.com");
        driver.manage().window().maximize();
        logger.info("Window is maximize here ");

        // Locate the web element
        WebElement logo = driver.findElement(By.xpath("//*[@id=\"app\"]/header/a/img"));


        File screenshots = logo.getScreenshotAs(OutputType.FILE);

        String screenshotDirectory ="C:\\Users\\Vivek\\Vivek_Personal\\simulator\\untitled\\";

        String filedestination = screenshotDirectory + getClass() + "_" + System.currentTimeMillis() + ".png";

        try
        {
            FileUtils.copyFile(screenshots,new File(filedestination));
        } catch (IOException e) {
            throw new RuntimeException(e.getMessage());
        }

        System.out.println("Not closing the browser here");
        logger.info("Not cloing the browser here ");



        //Screenshot screenshot = new Ashot().takeScreenshot(driver);



        // Locate the web element
        //  WebElement logo = driver.findElement(By.xpath("//*[@id=\"app\"]/header/a/img"));
Thread.sleep(2000);

        Screenshot s=new AShot().shootingStrategy(ShootingStrategies.viewportPasting(2000)).takeScreenshot(driver);
        ImageIO.write(s.getImage(),"PNG",new File(filedestination));


    }
}
