import org.openqa.selenium.By;
import org.openqa.selenium.JavascriptExecutor;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;
import org.testng.annotations.Test;

import java.util.Iterator;
import java.util.Set;

public class ChildWindow {


    @Test
    public void chwindow() throws InterruptedException {

        System.setProperty("webdriver.chrome.driver", "D:\\Intellij\\chromedriver.exe");
        WebDriver driver = new ChromeDriver();
        driver.manage().window().maximize();
        driver.get("https://demoqa.com/browser-windows");

        //to perform Scroll on application using Selenium
        JavascriptExecutor js = (JavascriptExecutor) driver;
        js.executeScript("window.scrollBy(0,150)");


        Thread.sleep(3000);// Open new window by clicking the button
        driver.findElement(By.id("windowButton")).click();
        //.click();
        System.out.println("New Popup appear");


        //using the getWindowhandler

        String mainwindowhandle = driver.getWindowHandle();
        Set<String> allwindowhandles = driver.getWindowHandles();

        // Now we will use the iterator

        Iterator<String> iterator = allwindowhandles.iterator();

        // using a while loop

        while (iterator.hasNext()) {
            String childwindow = iterator.next();
            if (!mainwindowhandle.equalsIgnoreCase(childwindow)) {
                ;
                driver.switchTo().window(childwindow);


                // Click on the new window element and read the text displayed on the window
                WebElement text = driver.findElement(By.xpath("//body/h1[@id='sampleHeading']"));

                Thread.sleep(2000);

//            driver.close();
                System.out.println("Child window should get closed");


                // Fetching the text using method and printing it
                System.out.println("Element found using text: " + text.getText());
            }
            //  driver.quit();
        }
        driver.switchTo().window(mainwindowhandle);
        System.out.println("Title of main window"   + driver.getTitle());

    }
}
