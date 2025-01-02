import org.openqa.selenium.By;
import org.openqa.selenium.JavascriptExecutor;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.testng.annotations.Test;

import java.util.List;

public class Iframes {


    @Test
    public void frames() throws InterruptedException {

        // public static void main(String[] args) throws InterruptedException {
        System.setProperty("webdriver.chrome.driver", "D:\\Intellij\\chromedriver.exe");
        WebDriver driver = new ChromeDriver();
        driver.get("https://demoqa.com/frames");
        driver.manage().window().maximize();

        //By executing a java script
        JavascriptExecutor exe = (JavascriptExecutor) driver;
        Integer numberOfFrames = Integer.parseInt(exe.executeScript("return window.length").toString());
        System.out.println("Number of iframes on the page are " + numberOfFrames);

        //By finding all the web elements using iframe tag
        List<WebElement> iframeElements = driver.findElements(By.tagName("iframe"));
        System.out.println("The total number of iframes are " + iframeElements.size());


        // Now swtich to framework using index

        WebElement ifff = iframeElements.get(1);
        System.out.println(ifff.getAttribute("id"));
       // String abc =ifff.getAttribute("id");
        //System.out.println("Print the class name = " + abc);

        //System.out.println("Ttile  the class name = " + iframeElements.ge);



        driver.switchTo().frame(6);
        driver.switchTo().parentFrame();






    }
}