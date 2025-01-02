import java.time.Duration;
import java.util.concurrent.TimeUnit;

import com.google.common.annotations.VisibleForTesting;
import org.openqa.selenium.*;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.firefox.FirefoxDriver;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

public class FirstTestInSelenium {

 private WebDriver driver;

 //@Test
        public void setUp() throws Exception {
            driver = new FirefoxDriver();
            //baseUrl = "http://www.google.com";
            driver.get("http://www.google.com");
            driver.manage().window().maximize();
     driver.manage().timeouts().implicitlyWait(10, TimeUnit.SECONDS);
   //  driver.findElement(By.xpath("//button[@class='M6CB1c rr4y5c' and contains(text(),'Stay signed out')]")).click();
     //driver.findElement(By.className("M6CB1c rr4y5c")).click();

     // Execute JavaScript to click on the "Stay Signed Out" button
     ((JavascriptExecutor) driver).executeScript("document.querySelector('button:contains(\"Stay signed out\")').click();"); // Conti
            driver.manage().timeouts().implicitlyWait(20, TimeUnit.SECONDS);
     WebElement element = driver.findElement(By.id("lst-ib"));
     element.sendKeys("Selenium WebDriver Interview questions");
     element.sendKeys(Keys.RETURN);

        }

@Test
        public void browserlaunch() throws InterruptedException
        {
       // public static void main(String[] args) throws InterruptedException {
// TODO Auto-generated method stub

//setting the driver executable
            System.setProperty("webdriver.chrome.driver", "D:\\Intellij\\chromedriver.exe");

//Initiating your chromedriver
            WebDriver driver=new ChromeDriver();

//Applied wait time


            //    driver.manage().timeouts().implicitlyWait(50, TimeUnit.SECONDS);
//maximize window
            driver.manage().window().maximize();

//open browser with desried URL
            driver.get("https://www.google.co.in");

            Alert alert = driver.switchTo().alert();

            WebDriverWait wait = new WebDriverWait(driver, Duration.ofSeconds(10));
            try
            {

                //String alertMessage= driver.switchTo().alert().getText();

                WebElement popUpCloseButton = wait.until(ExpectedConditions.elementToBeClickable(By.xpath("//button[contains(@class,'M6CB1c rr4y5c')]")));
                // Update the XPath with the actual close button's XPath popUpCloseButton.click();

                String alertMessage= driver.switchTo().alert().getText();
                popUpCloseButton.click();
                }
                catch (Exception e) { System.out.println("No pop-up appeared.");
            }




            WebElement element = driver.findElement(By.id("lst-ib"));
            element.sendKeys("Selenium WebDriver Interview questions");
            element.sendKeys(Keys.RETURN);


            Thread.sleep(9000);

System.out.println(" Brosser launch and going to closed here");
//closing the browser
            driver.close();

        }

    }